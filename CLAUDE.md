# Repo: ai-mcp

Part of **ETC AI Platform** ecosystem. Workspace root: `D:/AI-Platform/`.

For ecosystem-wide context:
- **`../../CLAUDE.md`** — maintainer manifesto
- **`../../ecosystem.yaml`** — machine inventory (this repo's entry: `id: ai-mcp`)
- **`../../docs/`** — governance hub

## This repo's role

MCP server cho ETC technical document rendering (DOCX/XLSX/PDF) via FastAPI + Python. Built into Docker image `o0mrblack0o/etc-platform` (image name retained per ECO-002 sub-decision cho member backward-compat). Consumers: `ai-studio`, `ai-kit` skills, `/generate-docs` pipeline.

## Internal layout

- `src/etc_platform/` — Python package (module name `etc_platform` retained as Python identifier; package decoupled from repo name)
- `tests/{unit,integration,testcases}/`
- `tools/`, `scripts/`, `integrations/`, `examples/`
- `Dockerfile`, `docker-compose.yaml`, `pyproject.toml`
- `docs/` — internal API docs, contract specs, repo-specific ADRs

## Release flow

`pwsh ../../scripts/release-mcp.ps1 -BumpTeam` builds Docker image, pushes to Docker Hub, bumps `../ai-kit-source/mcp/etc-platform/.env.example`. Full procedure: `../../docs/runbooks/release-flow.md` (Track 2).

## Internal ADR namespace

Use `AM-NNN` prefix for repo-specific ADRs (folder: `docs/adr/`). Cross-ecosystem decisions → `../../docs/adr/ECO-NNN-*.md`.

## Cross-ecosystem refs

Run `node ../../scripts/platform.mjs query adr:affecting '%ai-mcp%'` for ADRs touching this repo.
