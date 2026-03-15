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

## SEC 8-K Item Codes → Risk Signals
Item 1.01 = Material Definitive Agreement
Item 1.02 = Termination of Material Agreement  → CONTRACT_RENEWAL_AT_RISK
Item 2.01 = Completion of Acquisition          → TAKEOVER_BID
Item 2.05 = Departure of Directors/Officers    → EXECUTIVE_DEPARTURE
Item 2.06 = Material Impairment               → EARNINGS_MISS
Item 3.01 = Delisting Notice → EARNINGS_MISS (closest signal,
            or add DELISTING_RISK to RiskSignal enum in Month 2)
Item 8.01 = Other Events (catch-all)
