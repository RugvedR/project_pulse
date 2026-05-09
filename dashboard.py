"""
Pulse Financial Analytics Dashboard
-------------------------------------
Streamlit is a synchronous framework. This dashboard uses a dedicated
synchronous SQLAlchemy engine (psycopg2) to query Supabase. No asyncio
is used here — that is correct and intentional. The async engine is
only used by the Telegram bot (main.py).

Data is cached for 5 minutes per user/period combination.
Refresh manually using the sidebar button.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from pulse.config import settings

# ---------------------------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Pulse Dashboard",
    page_icon="🫀",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric {
        background-color: #1e2130;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #3e4259;
    }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Synchronous DB Engine (psycopg2 — correct for Streamlit)
# ---------------------------------------------------------------------------
@st.cache_resource
def get_sync_engine():
    """
    Creates a single synchronous SQLAlchemy engine for the lifetime of the
    Streamlit process. Uses psycopg2 (not asyncpg) because Streamlit is sync.
    """
    raw_url = settings.DATABASE_URL_RAW
    # Ensure we use the synchronous psycopg2 driver
    if raw_url.startswith("postgresql://"):
        sync_url = raw_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    elif raw_url.startswith("sqlite"):
        sync_url = raw_url.replace("sqlite+aiosqlite", "sqlite")
    else:
        sync_url = raw_url
    return create_engine(sync_url, pool_pre_ping=True)


def get_db_session():
    engine = get_sync_engine()
    Session = sessionmaker(bind=engine)
    return Session()

# ---------------------------------------------------------------------------
# OTP Authentication (Phase 6 — per-user, no shared password)
# ---------------------------------------------------------------------------
def verify_otp(thread_id: str, token: str) -> bool:
    """
    Check the submitted OTP against the database.
    Uses the same synchronous engine so no async complications.
    """
    with get_db_session() as session:
        row = session.execute(
            text(
                "SELECT auth_token, token_expires_at FROM user_profiles "
                "WHERE thread_id = :tid"
            ),
            {"tid": thread_id},
        ).fetchone()

        if not row or not row[0] or not row[1]:
            return False

        stored_token = row[0]
        expires_at = row[1]

        # Normalise timezone
        now = datetime.utcnow()
        if hasattr(expires_at, "tzinfo") and expires_at.tzinfo is not None:
            import pytz
            now = datetime.now(pytz.utc)

        if stored_token != token or expires_at < now:
            return False

        # Single-use: clear the token immediately
        session.execute(
            text(
                "UPDATE user_profiles "
                "SET auth_token = NULL, token_expires_at = NULL "
                "WHERE thread_id = :tid"
            ),
            {"tid": thread_id},
        )
        session.commit()
        return True


def check_login() -> bool:
    """
    Renders the OTP login form and returns True once a user is authenticated.
    The authenticated user_id is stored in st.session_state for the session.
    """
    if st.session_state.get("authenticated"):
        return True

    st.title("🫀 Pulse Analytics")
    st.markdown("### Secure Login")
    st.info(
        "Get your access code by sending `/dashboard` to your Pulse bot on Telegram.",
        icon="💬",
    )

    with st.form("login_form"):
        user_id_input = st.text_input("Your Telegram User ID", placeholder="e.g. 1485978523")
        token_input = st.text_input("6-Digit Access Code", placeholder="e.g. 482910", max_chars=6)
        submitted = st.form_submit_button("Login →")

    if submitted:
        if not user_id_input or not token_input:
            st.error("Please fill in both fields.")
            return False

        if verify_otp(user_id_input.strip(), token_input.strip()):
            st.session_state["authenticated"] = True
            st.session_state["user_id"] = user_id_input.strip()
            st.rerun()
        else:
            st.error("❌ Invalid code or code has expired. Get a new one from the bot.")
            return False

    return False

# ---------------------------------------------------------------------------
# Data Fetchers — fully synchronous, cached per (user_id, days)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=300)
def fetch_kpis(user_id: str) -> dict:
    """Fetch KPI metrics for the current month."""
    now = datetime.utcnow()
    first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    with get_db_session() as session:
        total = session.execute(text(
            "SELECT COALESCE(SUM(amount), 0) FROM transactions "
            "WHERE thread_id = :uid AND timestamp >= :since"
        ), {"uid": user_id, "since": first_of_month}).scalar()

        count = session.execute(text(
            "SELECT COUNT(*) FROM transactions "
            "WHERE thread_id = :uid AND timestamp >= :since"
        ), {"uid": user_id, "since": first_of_month}).scalar()

        top_cat = session.execute(text(
            "SELECT category FROM transactions "
            "WHERE thread_id = :uid AND timestamp >= :since "
            "GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1"
        ), {"uid": user_id, "since": first_of_month}).scalar()

    days_elapsed = max((now - first_of_month).days + 1, 1)
    return {
        "total_spent_month": float(total or 0),
        "transaction_count": int(count or 0),
        "top_category": top_cat or "N/A",
        "days_in_month": days_elapsed,
    }


@st.cache_data(ttl=300)
def fetch_spending_by_category(user_id: str, days: int) -> list:
    """Fetch spending grouped by category."""
    since = datetime.utcnow() - timedelta(days=days)
    with get_db_session() as session:
        rows = session.execute(text(
            "SELECT category, SUM(amount) AS total FROM transactions "
            "WHERE thread_id = :uid AND timestamp >= :since "
            "GROUP BY category ORDER BY total DESC"
        ), {"uid": user_id, "since": since}).fetchall()
    return [{"category": r[0], "amount": float(r[1])} for r in rows]


@st.cache_data(ttl=300)
def fetch_daily_trends(user_id: str, days: int) -> list:
    """Fetch daily spending totals."""
    since = datetime.utcnow() - timedelta(days=days)
    with get_db_session() as session:
        rows = session.execute(text(
            "SELECT DATE(timestamp) AS day, SUM(amount) AS total FROM transactions "
            "WHERE thread_id = :uid AND timestamp >= :since "
            "GROUP BY day ORDER BY day"
        ), {"uid": user_id, "since": since}).fetchall()
    return [{"date": str(r[0]), "amount": float(r[1])} for r in rows]


@st.cache_data(ttl=300)
def fetch_recent_transactions(user_id: str, days: int) -> list:
    """Fetch recent transactions."""
    since = datetime.utcnow() - timedelta(days=days)
    with get_db_session() as session:
        rows = session.execute(text(
            "SELECT timestamp, vendor, category, amount, notes FROM transactions "
            "WHERE thread_id = :uid AND timestamp >= :since "
            "ORDER BY timestamp DESC LIMIT 100"
        ), {"uid": user_id, "since": since}).fetchall()
    return rows

# ---------------------------------------------------------------------------
# Main Dashboard
# ---------------------------------------------------------------------------
if check_login():
    # User ID is now locked to the authenticated session
    user_id = st.session_state["user_id"]

    st.title("🫀 Pulse Financial Analytics")
    st.markdown("---")

    # Sidebar
    st.sidebar.header("Filters")
    st.sidebar.text(f"🔑 Logged in as: {user_id}")
    lookback_days = st.sidebar.slider("Analysis Period (Days)", 1, 365, 30)

    if st.sidebar.button("🔄 Refresh Now"):
        st.cache_data.clear()
        st.rerun()

    if st.sidebar.button("🚪 Logout"):
        st.session_state.clear()
        st.rerun()

    # Fetch Data
    with st.spinner("Loading your financial data..."):
        kpis = fetch_kpis(user_id)
        cat_data = fetch_spending_by_category(user_id, lookback_days)
        trend_data = fetch_daily_trends(user_id, lookback_days)
        recent_txns = fetch_recent_transactions(user_id, lookback_days)

    # KPI Row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Monthly Spend", f"₹{kpis['total_spent_month']:,.2f}")
    with col2:
        avg_day = kpis['total_spent_month'] / kpis['days_in_month']
        st.metric("Avg / Day", f"₹{avg_day:,.2f}")
    with col3:
        st.metric("Transactions", kpis['transaction_count'])
    with col4:
        st.metric("Top Category", kpis['top_category'])

    st.markdown("<br>", unsafe_allow_html=True)

    # Charts
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
            st.info("No category data found for this period.")

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
            st.info("No trend data found for this period.")

    # Recent Transactions Table
    st.markdown("---")
    st.subheader("Recent Transactions")
    if recent_txns:
        txn_list = [
            {
                "Date": row[0].strftime("%Y-%m-%d %H:%M") if hasattr(row[0], 'strftime') else str(row[0]),
                "Vendor": row[1],
                "Category": row[2],
                "Amount": f"₹{row[3]:,.2f}",
                "Notes": row[4] or ""
            }
            for row in recent_txns
        ]
        st.table(pd.DataFrame(txn_list))
    else:
        st.write("No transactions recorded yet.")

    # Footer
    st.markdown("---")
    st.caption(f"Pulse Analytics Engine | Last synced: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
