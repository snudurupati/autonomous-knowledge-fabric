import streamlit as st
import pandas as pd
import sys
from pathlib import Path

# Add project root to sys.path to allow imports from graph, models, etc.
root_path = str(Path(__file__).resolve().parent.parent)
if root_path not in sys.path:
    sys.path.append(root_path)

from graph.memgraph_client import MemgraphClient
from datetime import datetime, timezone

st.set_page_config(page_title="AKF Account Intelligence", layout="wide")

st.title("🛡️ Autonomous Knowledge Fabric")
st.subheader("Real-time Account Risk Intelligence")

@st.cache_resource
def get_client():
    return MemgraphClient()

client = get_client()

# Sidebar for controls
st.sidebar.header("Controls")
if st.sidebar.button("Refresh Data"):
    st.cache_data.clear()

# Main Dashboard
col1, col2 = st.columns([2, 1])

with col1:
    st.write("### High Risk Accounts")
    high_risk = client.get_high_risk_accounts()
    
    if not high_risk:
        st.info("No high risk accounts detected yet.")
    else:
        df = pd.DataFrame(high_risk)
        # Rename columns for display
        df = df.rename(columns={
            "company": "Company Name",
            "score": "Risk Score",
            "level": "Risk Level",
            "signals": "Active Signals"
        })
        
        # Color coding for Risk Level
        def color_risk(val):
            if val == "CRITICAL": return "color: red; font-weight: bold"
            if val == "HIGH": return "color: orange"
            if val == "ELEVATED": return "color: yellow"
            return "color: green"

        st.dataframe(df.style.map(color_risk, subset=["Risk Level"]), use_container_width=True)

with col2:
    st.write("### Search Account")
    search_query = st.text_input("Enter company name...")
    if search_query:
        results = client.search_accounts(search_query)
        if not results:
            st.warning(f"No results for '{search_query}'")
        else:
            for res in results:
                with st.expander(f"{res['company_name']}"):
                    ctx = client.get_account_context(res['company_name'])
                    if ctx:
                        st.metric("Risk Score", f"{ctx['risk_score']}/100", ctx['risk_level'])
                        st.write(f"**Signals:** {', '.join(ctx['risk_signals']) or 'None'}")
                        st.write(f"**Last Updated:** {ctx['last_updated']}")
                        st.write("**Recent Events:**")
                        for event in ctx['recent_events']:
                            st.text_area("Event Detail", event, height=100, disabled=True)

# Footer/Status
st.divider()
st.caption(f"Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
