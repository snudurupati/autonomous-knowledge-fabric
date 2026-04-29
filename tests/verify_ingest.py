import logging
import sys
from engine.omnigraph.ingestion_sink import OmnigraphSink
from models.account_event import AccountEvent, EventSource, RiskSignal

logging.basicConfig(level=logging.INFO)

def verify():
    sink = OmnigraphSink(server_url="http://localhost:8080")
    event = AccountEvent(
        source=EventSource.SALESFORCE,
        company_name="Verification Corp",
        risk_signals=[RiskSignal.TAKEOVER_BID],
        raw_text="Manual verification event"
    )
    
    print(f"Attempting to ingest 1 event for '{event.company_name}'...")
    success = sink.ingest_event(event)
    if success:
        print("✅ Ingestion successful!")
    else:
        print("❌ Ingestion failed. Check logs.")
        sys.exit(1)

if __name__ == "__main__":
    verify()
