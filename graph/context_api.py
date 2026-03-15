# graph/context_api.py
# High-level context API for LLM agents — wraps MemgraphClient.

from graph.memgraph_client import MemgraphClient

_client: MemgraphClient | None = None


def _get_client() -> MemgraphClient:
    global _client
    if _client is None:
        _client = MemgraphClient()
    return _client


def freshness_label(age_seconds: int) -> str:
    """Return a human-readable freshness label for a given age in seconds."""
    if age_seconds < 60:
        return "LIVE (sub-60s)"
    elif age_seconds < 300:
        return "RECENT (60-300s)"
    else:
        return f"STALE ({age_seconds}s)"


def get_agent_context(company_name: str) -> str:
    """Return a formatted Account Intelligence Report for an LLM agent."""
    ctx = _get_client().get_account_context(company_name)
    if ctx is None:
        return f"No data found for '{company_name}'."

    age = ctx["context_age_seconds"]
    freshness = freshness_label(age)
    signals_str = ", ".join(ctx["risk_signals"]) if ctx["risk_signals"] else "None detected"
    events_str = "\n".join(f"- {e}" for e in ctx["recent_events"]) or "- (none)"

    return (
        f"ACCOUNT INTELLIGENCE REPORT\n"
        f"Company: {ctx['company_name']}\n"
        f"Last Updated: {ctx['last_updated']} ({age} seconds ago)\n"
        f"Risk Signals: {signals_str}\n"
        f"Recent Events ({ctx['total_events']} total):\n{events_str}\n"
        f"Context Freshness: {freshness}"
    )
