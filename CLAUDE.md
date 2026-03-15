# stream-graph-rag — CLAUDE.md

## Project Mission
Reference architecture for real-time Account Intelligence using
Pathway (stream processing) + Memgraph (knowledge graph).

## Core Use Case
Sales Director QBR scenario: detect SEC filings + CRM events
and update account risk score in <60 seconds.

## Stack
- Stream processor: Pathway (Python/Rust, single container)
- Graph DB: Memgraph (Docker, port 7687)
- Schema validation: Pydantic
- Entity resolution: 3-Tier (Hash → Graph Neighbor → LLM Judge)
- Observability: OpenTelemetry from Day 1
- Demo UI: Streamlit

## Current Sprint
[Update this every sprint]

## Conventions
- All Pydantic models live in /models
- Pathway pipelines live in /pipelines
- Tests use pytest, run via `.venv312/bin/pytest tests/`
- Always use `.venv312/bin/python` (Python 3.12) — the default `.venv` is Python 3.14 which lacks pyarrow/Pathway wheels
- Use `python3.12 -m pip` instead of `.venv312/bin/pip` — the pip shebang breaks after project renames
- Never commit `.venv312/` to git — it contains binaries >100MB that exceed GitHub's limit (it's in .gitignore)
- Memgraph auth is `admin/admin` (set via `MEMGRAPH_USER` / `MEMGRAPH_PASSWORD` in docker-compose.yml) — default no-auth will fail
- Docker stack starts with `docker compose up -d`
- `timeout` is not available on macOS (GNU coreutils only) — use Python-native loop control instead of shell `timeout`

## Claude Code Notes
- Custom commands live in .claude/commands/
- After adding/editing any command file, quit and relaunch 
  Claude Code for changes to take effect
- Sprint rhythm: /sprint-start → work → /sprint-end
- Run /compact mid-sprint if Claude starts forgetting context

## Running Scripts
- Always run scripts as modules from project root:
  `python -m pipelines.script_name`
- Never use `python pipelines/script_name.py` directly
- All packages have __init__.py files in models/, pipelines/, 
  graph/, scoring/, observability/
