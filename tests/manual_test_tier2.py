from models.account_event import AccountEvent
from graph.memgraph_client import MemgraphClient
from datetime import datetime, timezone

client = MemgraphClient()

# Event A: Creates the initial node
event_a = AccountEvent(
    source="SALESFORCE",
    company_name="Stark Industries",
    company_domain="stark.com",  # Fixed to match Pydantic schema
    timestamp=datetime.now(timezone.utc),
    raw_text="Opportunity stage moved to Closed Won for Stark Industries."
)
client.upsert_event(event_a)
print("Fired Event A: Created 'Stark Industries'")

# Event B: Different name, same domain. 
# Tier 1 will fail (hashes don't match). Tier 2 should catch the 'stark.com' domain.
event_b = AccountEvent(
    source="ZENDESK",
    company_name="Stark Global Corp",
    company_domain="stark.com",  # Fixed to match Pydantic schema
    timestamp=datetime.now(timezone.utc),
    raw_text="Critical SLA breach on Stark Global Corp main server cluster."
)
client.upsert_event(event_b)
print("Fired Event B: 'Stark Global Corp' (Should trigger Tier 2 merge)")