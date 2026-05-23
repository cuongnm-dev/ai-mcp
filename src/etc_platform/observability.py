"""MCP observability — log each tool call to observation_log + HTTP query route.

Per ECO-020 (artifact-studio Domain 4): cloud MCP must record per-tool
invocations to enable client analytics. Implementation:

  1. monkey-patch FastMCP.call_tool — wrap with timing + DB insert
  2. add /observation/query custom_route — paginated dump for sidecar import

Writes go to observation_log table (already exists per registry/db.py).
PII safety: args raw NEVER stored; only sha256[:32] of args JSON.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from typing import Any

from etc_platform.registry.db import _get_conn, utc_iso

log = logging.getLogger("etc-platform.obs")

# ─── PII scrubbers (NĐ 13/2023) ───
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_VN_RE = re.compile(r"\b(?:\+?84|0)(?:3\d|5\d|7\d|8\d|9\d)\d{7,8}\b")
_NID_RE = re.compile(r"\b\d{9,12}\b")  # CMND/CCCD


def _scrub(s: str) -> str:
    """Scrub PII before hashing — defense in depth even though we only hash."""
    s = _EMAIL_RE.sub("[EMAIL]", s)
    s = _PHONE_VN_RE.sub("[PHONE]", s)
    s = _NID_RE.sub("[NID]", s)
    return s


def args_hash(args: Any) -> str:
    """sha256[:32] of JSON-canonicalized + PII-scrubbed args."""
    try:
        text = json.dumps(args, sort_keys=True, ensure_ascii=False, default=str)
    except Exception:
        text = repr(args)[:1000]
    return hashlib.sha256(_scrub(text).encode("utf-8")).hexdigest()[:32]


def record_invocation(
    *,
    tool: str,
    args_summary: str,
    elapsed_ms: int,
    success: bool,
    result_size: int = 0,
    error_kind: str | None = None,
) -> None:
    """Write one row to observation_log. Never raises."""
    try:
        conn = _get_conn()
        conn.execute(
            "INSERT INTO observation_log "
            "(timestamp, tool, args_summary, result_size, elapsed_ms, success, error_kind) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (utc_iso(), tool, args_summary, result_size, elapsed_ms, 1 if success else 0, error_kind),
        )
    except Exception as exc:  # pragma: no cover
        log.warning("observation_log write failed: %s", exc)


def wrap_mcp_call_tool(mcp_instance: Any) -> None:
    """Monkey-patch FastMCP.call_tool to record invocations.

    Idempotent — sets `_observability_wrapped` flag on instance.
    """
    if getattr(mcp_instance, "_observability_wrapped", False):
        return
    original = mcp_instance.call_tool

    async def wrapped_call_tool(name: str, arguments: dict[str, Any], **kwargs: Any) -> Any:
        t0 = time.monotonic()
        success = True
        error_kind: str | None = None
        result: Any = None
        try:
            result = await original(name, arguments, **kwargs)
            return result
        except Exception as exc:
            success = False
            error_kind = type(exc).__name__
            raise
        finally:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            result_size = 0
            try:
                if result is not None:
                    result_size = len(json.dumps(result, default=str))
            except Exception:
                result_size = 0
            record_invocation(
                tool=name,
                args_summary=args_hash(arguments),
                elapsed_ms=elapsed_ms,
                success=success,
                result_size=result_size,
                error_kind=error_kind,
            )

    mcp_instance.call_tool = wrapped_call_tool  # type: ignore[assignment]
    mcp_instance._observability_wrapped = True
    log.info("MCP observability hook installed (call_tool wrapped)")


def register_observation_routes(mcp_instance: Any) -> None:
    """Add custom_route `/observation/query` for sidecar import.

    Auth: optional X-API-Key check against ETC_PLATFORM_API_KEY env.
    Query params:
      - since: ISO timestamp, only events ≥ this
      - tool: filter by tool name (LIKE %tool%)
      - limit: 1..2000, default 500
      - status: 'success' | 'error' | 'all'
    """
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    expected_key = os.environ.get("ETC_PLATFORM_API_KEY")

    @mcp_instance.custom_route("/observation/query", methods=["GET"])
    async def observation_query(request: Request) -> JSONResponse:
        if expected_key:
            got = request.headers.get("X-API-Key", "")
            if got != expected_key:
                return JSONResponse(
                    {"error": "auth_required"}, status_code=401
                )
        params = request.query_params
        since = params.get("since")
        tool_filter = params.get("tool")
        status_filter = params.get("status", "all")
        try:
            limit = max(1, min(2000, int(params.get("limit", "500"))))
        except ValueError:
            limit = 500
        try:
            conn = _get_conn()
            where = []
            args: list[Any] = []
            if since:
                where.append("timestamp >= ?")
                args.append(since)
            if tool_filter:
                where.append("tool LIKE ?")
                args.append(f"%{tool_filter}%")
            if status_filter == "success":
                where.append("success = 1")
            elif status_filter == "error":
                where.append("success = 0")
            sql = "SELECT timestamp, tool, args_summary, result_size, elapsed_ms, success, error_kind FROM observation_log"
            if where:
                sql += " WHERE " + " AND ".join(where)
            sql += " ORDER BY id DESC LIMIT ?"
            args.append(limit)
            cur = conn.execute(sql, args)
            rows = [
                {
                    "ts": r["timestamp"],
                    "tool": r["tool"],
                    "args_hash": r["args_summary"],
                    "result_size": r["result_size"],
                    "elapsed_ms": r["elapsed_ms"],
                    "success": bool(r["success"]),
                    "error_kind": r["error_kind"],
                }
                for r in cur.fetchall()
            ]
            return JSONResponse({"events": rows, "returned": len(rows)})
        except Exception as exc:
            return JSONResponse(
                {"error": "query_failed", "message": str(exc)}, status_code=500
            )

    @mcp_instance.custom_route("/observation/summary", methods=["GET"])
    async def observation_summary(_request: Request) -> JSONResponse:
        try:
            conn = _get_conn()
            total = conn.execute(
                "SELECT COUNT(*) AS n FROM observation_log"
            ).fetchone()["n"]
            errors = conn.execute(
                "SELECT COUNT(*) AS n FROM observation_log WHERE success = 0"
            ).fetchone()["n"]
            by_tool_rows = conn.execute(
                "SELECT tool, COUNT(*) AS n, AVG(elapsed_ms) AS avg_ms, "
                "SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) AS errs "
                "FROM observation_log GROUP BY tool ORDER BY n DESC LIMIT 50"
            ).fetchall()
            by_tool = [
                {
                    "tool": r["tool"],
                    "count": r["n"],
                    "avg_ms": round(r["avg_ms"] or 0, 1),
                    "errors": r["errs"],
                }
                for r in by_tool_rows
            ]
            return JSONResponse(
                {
                    "total": total,
                    "errors": errors,
                    "error_rate_pct": (errors / total * 100) if total else 0,
                    "by_tool": by_tool,
                }
            )
        except Exception as exc:
            return JSONResponse(
                {"error": "summary_failed", "message": str(exc)}, status_code=500
            )

    log.info(
        "MCP observation routes registered: /observation/query, /observation/summary"
    )


def install(mcp_instance: Any) -> None:
    """One-call setup: wrap call_tool + register HTTP routes."""
    wrap_mcp_call_tool(mcp_instance)
    register_observation_routes(mcp_instance)
