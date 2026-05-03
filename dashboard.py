import streamlit as st
import asyncio
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

from pulse.config import settings
from pulse.analytics import get_spending_by_category, get_daily_spending_trends, get_kpi_metrics
from pulse.db.queries import get_recent_transactions

# ---------------------------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Pulse Dashboard",
    page_icon="🫀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for premium look
st.markdown("""
    <style>
    .main {
        background-color: #0e1117;
    }
    .stMetric {
        background-color: #1e2130;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #3e4259;
    }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
def check_password():
    """Returns `True` if the user had the correct password."""
    def password_entered():
        if st.session_state["password"] == settings.DASHBOARD_PASSWORD:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # don't store password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # First run, show input for password.
        st.text_input(
            "Enter Dashboard Password", type="password", on_change=password_entered, key="password"
        )
        return False
    elif not st.session_state["password_correct"]:
        # Password incorrect, show input + error.
        st.text_input(
            "Enter Dashboard Password", type="password", on_change=password_entered, key="password"
        )
        st.error("😕 Password incorrect")
        return False
    else:
        # Password correct.
        return True

# ---------------------------------------------------------------------------
# Data Fetchers (Async Bridge)
# ---------------------------------------------------------------------------
def run_async(coro):
    return asyncio.run(coro)

# ---------------------------------------------------------------------------
# Main Dashboard
# ---------------------------------------------------------------------------
if check_password():
    st.title("🫀 Pulse Financial Analytics")
    st.markdown("---")

    # Sidebar Filters
    st.sidebar.header("Filters")
    user_id = st.sidebar.text_input("User ID (Thread ID)", value="1485978523")
    lookback_days = st.sidebar.slider("Analysis Period (Days)", 1, 365, 30)

    # Fetch Data
    with st.spinner("Fetching data from Pulse..."):
        kpis = run_async(get_kpi_metrics(user_id))
        cat_data = run_async(get_spending_by_category(user_id, lookback_days))
        trend_data = run_async(get_daily_spending_trends(user_id, lookback_days))
        # Now respects the slider days and shows up to 100 entries
        recent_txns = run_async(get_recent_transactions(user_id, days=lookback_days, limit=100))

    # KPI Row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Monthly Spend", f"₹{kpis['total_spent_month']:,.2f}")
    with col2:
        st.metric("Avg / Day", f"₹{(kpis['total_spent_month']/kpis['days_in_month']):,.2f}")
    with col3:
        st.metric("Transactions", kpis['transaction_count'])
    with col4:
        st.metric("Top Category", kpis['top_category'])

    st.markdown("<br>", unsafe_allow_html=True)

    # Charts Row
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.subheader("Spending by Category")
        if cat_data:
            df_cat = pd.DataFrame(cat_data)
            fig_pie = px.pie(
                df_cat, values='amount', names='category', 
                hole=0.4, color_discrete_sequence=px.colors.sequential.RdBu
            )
            fig_pie.update_layout(margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No data found for the selected period.")

    with chart_col2:
        st.subheader("Daily Spending Trend")
        if trend_data:
            df_trend = pd.DataFrame(trend_data)
            fig_area = px.area(
                df_trend, x='date', y='amount',
                line_shape='spline', color_discrete_sequence=['#ff4b4b']
            )
            fig_area.update_layout(xaxis_title=None, yaxis_title="Amount (INR)")
            st.plotly_chart(fig_area, use_container_width=True)
        else:
            st.info("No data found for the selected period.")

    # Recent Transactions Table
    st.markdown("---")
    st.subheader("Recent Transactions")
    if recent_txns:
        txn_list = []
        for t in recent_txns:
            txn_list.append({
                "Date": t.timestamp.strftime("%Y-%m-%d %H:%M"),
                "Vendor": t.vendor,
                "Category": t.category,
                "Amount": f"₹{t.amount:,.2f}",
                "Notes": t.notes or ""
            })
        st.table(pd.DataFrame(txn_list))
    else:
        st.write("No transactions recorded yet.")

    # Footer
    st.markdown("---")
    st.caption(f"Pulse Analytics Engine | Last synced: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
