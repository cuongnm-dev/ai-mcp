# Repo: ai-mcp

Part of **ETC AI Platform** — workspace root `D:/AI-Platform/`.

For session state + ecosystem rules, FIRST run from workspace root:

- `node scripts/platform.mjs start --human` (ecosystem JSON state)
- Read `D:/AI-Platform/AGENTS.md` (rule_precedence, hard_rules R1-R7, write_locations, edit_flow)
- Read `~/.claude/projects/D--AI-Platform/memory/MEMORY.md` (user preferences)

This repo's role: MCP server (FastMCP Python, Docker image `o0mrblack0o/etc-platform` — image name retained per ECO-002 sub-decision for member backward-compat). Provides ~24 tools: Office rendering (DOCX/XLSX/PDF), KB query/save, DEDUP, template registry, schema validation. Endpoint: `localhost:8001/sse` (MCP SSE) + `localhost:8001/` (HTTP API). Consumers: ai-studio, ai-kit skills, `/generate-docs` pipeline.

Internal Python package name: `etc_platform` (decoupled from repo name; identifier retained for backward-compat).

ADR namespace: `AM-NNN` in `docs/adr/`. Cross-ecosystem → `../../docs/adr/ECO-NNN-*.md`. ADR-005 (CLI-first, MCP retired for SDLC scope — Office + KB + DEDUP only).

Release flow: `pwsh ../../scripts/release-mcp.ps1 -BumpTeam` from meta-repo (CD-8.A Office MCP scope).

SINGLE SOURCE OF TRUTH for architecture / decisions / rules: meta-repo. Do NOT duplicate here.
