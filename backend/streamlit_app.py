"""
Supplier Risk Scan — Frontend Dashboard

A polished Streamlit UI that consumes the backend API via ASGITransport
and displays supplier risk data with charts, KPIs, and interactive filters.

Usage (from backend/ directory):
    uv run --group dev streamlit run streamlit_app.py
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from collections import Counter

import altair as alt
import pandas as pd
import streamlit as st
from httpx import AsyncClient, ASGITransport
from app.main import create_app
from app.mock_data import generate_suppliers

# ── Page config (must be first Streamlit command) ────────────────────────
st.set_page_config(
    page_title="Supplier Risk Scan — Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ───────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* ── Global ── */
    .main > div { padding-top: 1rem; }
    .stApp { background: #0f0f0f; }
    h1, h2, h3 { font-weight: 600 !important; color: #ffffff !important; }
    p, li, div, span { color: #e0e0e0; }

    /* ── KPI Cards ── */
    .kpi-card {
        background: #1a1a1a;
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.4);
        border: 1px solid #333333;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.5);
    }
    .kpi-card .label {
        font-size: 0.8rem;
        font-weight: 500;
        color: #a0a0a0;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-bottom: 0.3rem;
    }
    .kpi-card .value {
        font-size: 1.8rem;
        font-weight: 700;
        line-height: 1.2;
    }
    .kpi-card .sub {
        font-size: 0.8rem;
        color: #888888;
        margin-top: 0.15rem;
    }

    /* ── Risk badges ── */
    .risk-badge {
        display: inline-block;
        padding: 0.15rem 0.7rem;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.02em;
    }
    .risk-critical { background: #450a0a; color: #fca5a5; border: 1px solid #dc2626; }
    .risk-high     { background: #431407; color: #fdba74; border: 1px solid #ea580c; }
    .risk-medium   { background: #422006; color: #fde047; border: 1px solid #ca8a04; }
    .risk-low      { background: #052e16; color: #86efac; border: 1px solid #16a34a; }

    /* ── Trend tags ── */
    .trend-up   { color: #fca5a5; }
    .trend-down { color: #86efac; }
    .trend-flat { color: #a0a0a0; }

    /* ── Alert cards ── */
    .alert-card {
        background: #1a1a1a;
        border-radius: 10px;
        padding: 1rem 1.2rem;
        border-left: 4px solid;
        margin-bottom: 0.6rem;
        box-shadow: 0 1px 2px rgba(0,0,0,0.3);
        transition: opacity 0.2s;
    }
    .alert-card.critical { border-left-color: #dc2626; }
    .alert-card.high     { border-left-color: #ea580c; }
    .alert-card.acked    { opacity: 0.45; }

    /* ── Section headers ── */
    .section-header {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 0.5rem;
    }
    .section-header h3 { margin: 0; }

    /* ── Supplier row ── */
    .supplier-row {
        background: #1a1a1a;
        border-radius: 8px;
        padding: 0.7rem 1rem;
        border: 1px solid #333333;
        cursor: pointer;
        transition: background 0.1s;
    }
    .supplier-row:hover { background: #2a2a2a; }

    /* ── Footer ── */
    .footer { text-align: center; color: #888888; font-size: 0.75rem; padding: 1rem 0; }

    /* Streamlit overrides */
    .stTabs [data-baseweb="tab-list"] { gap: 0.5rem; }
    .stTabs [data-baseweb="tab"] { border-radius: 8px 8px 0 0; padding: 0.5rem 1rem; }
    div[data-testid="stMetricValue"] { font-size: 1.6rem !important; font-weight: 700 !important; color: #ffffff !important; }
    div[data-testid="stMetricLabel"] { font-size: 0.75rem !important; text-transform: uppercase; letter-spacing: 0.04em; color: #a0a0a0; }

    /* Data table */
    .data-table { font-size: 0.85rem; color: #e0e0e0; }
    .data-table thead th { background: #1a1a1a; font-weight: 600; color: #cccccc; border-bottom: 1px solid #333; }
    .data-table td { border-bottom: 1px solid #222; padding: 0.4rem 0.5rem; }

    /* Scrollbar */
    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-track { background: #0f0f0f; }
    ::-webkit-scrollbar-thumb { background: #444; border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: #555; }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
#  DATA LAYER
# ═══════════════════════════════════════════════════════════════════════════

@st.cache_resource
def get_backend():
    """Create and cache the FastAPI app with initialised data."""
    application = create_app()
    suppliers_list = generate_suppliers()
    application.state.suppliers = {s.supplier_id: s for s in suppliers_list}
    all_alerts = []
    for s in suppliers_list:
        all_alerts.extend(s.alerts)
    application.state.alerts = all_alerts
    application.state.alert_engine = None
    return application


def run_async(coro):
    """Run an async coroutine from Streamlit's sync context."""
    return asyncio.run(coro)


def fetch_data(endpoint: str) -> tuple[int, Any]:
    """Make a real API call through the in-process backend."""
    app = get_backend()
    transport = ASGITransport(app=app)

    async def _call():
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            try:
                resp = await client.get(endpoint)
                try:
                    data = resp.json()
                except Exception:
                    data = resp.text
                return resp.status_code, data
            except Exception as e:
                return 0, {"error": str(e)}

    return run_async(_call())


@st.cache_data(ttl=5)
def get_stats():
    """Fetch portfolio stats."""
    _, data = fetch_data("/stats")
    return data if isinstance(data, dict) else {}


@st.cache_data(ttl=5)
def get_suppliers():
    """Fetch all suppliers."""
    _, data = fetch_data("/suppliers")
    return data if isinstance(data, list) else []


@st.cache_data(ttl=5)
def get_supplier_detail(supplier_id: str):
    """Fetch a single supplier by ID."""
    _, data = fetch_data(f"/suppliers/{supplier_id}")
    return data if isinstance(data, dict) else {}


@st.cache_data(ttl=5)
def get_alerts(severity: str | None = None,
               acknowledged: bool | None = None,
               supplier_id: str | None = None):
    """Fetch alerts with optional filters."""
    params = {}
    if severity:
        params["severity"] = severity
    if acknowledged is not None:
        params["acknowledged"] = str(acknowledged).lower()
    if supplier_id:
        params["supplier_id"] = supplier_id
    query = "&".join(f"{k}={v}" for k, v in params.items())
    endpoint = f"/alerts?{query}" if query else "/alerts"
    _, data = fetch_data(endpoint)
    return data if isinstance(data, list) else []


def acknowledge_alert(alert_id: str):
    """Acknowledge a single alert via API."""
    app = get_backend()
    transport = ASGITransport(app=app)

    async def _call():
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.patch(f"/alerts/{alert_id}/acknowledge")
            return resp.status_code, resp.json() if resp.text else {}

    return run_async(_call())


def bulk_acknowledge(alert_ids: list[str]):
    """Bulk acknowledge alerts via API."""
    app = get_backend()
    transport = ASGITransport(app=app)

    async def _call():
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/alerts/bulk-acknowledge", json={"alert_ids": alert_ids})
            return resp.status_code, resp.json() if resp.text else {}

    return run_async(_call())


# ═══════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def risk_badge_html(level: str) -> str:
    level = level.upper()
    css = {"CRITICAL": "risk-critical", "HIGH": "risk-high",
           "MEDIUM": "risk-medium", "LOW": "risk-low"}.get(level, "risk-low")
    return f'<span class="risk-badge {css}">{level}</span>'


def trend_arrow(trend: str) -> str:
    if trend == "DETERIORATING":
        return "🔺"
    if trend == "IMPROVING":
        return "🔻"
    return "➖"


def score_color(score: float) -> str:
    if score >= 80:
        return "#dc2626"
    if score >= 65:
        return "#ea580c"
    if score >= 40:
        return "#ca8a04"
    return "#16a34a"


# ═══════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════

def render_sidebar():
    stats = get_stats()
    suppliers = get_suppliers()

    with st.sidebar:
        st.markdown("""
        <div style="display:flex;align-items:center;gap:0.6rem;margin-bottom:0.5rem;">
            <span style="font-size:1.8rem;">🛡️</span>
            <div>
                <div style="font-weight:700;font-size:1.1rem;line-height:1.2;">Supplier Risk</div>
                <div style="font-size:0.7rem;color:#888888;text-transform:uppercase;letter-spacing:0.05em;">Dashboard</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.divider()

        # Navigation
        page = st.radio(
            "Navigate",
            ["📊  Portfolio", "🏢  Suppliers", "🔔  Alerts"],
            label_visibility="collapsed",
            key="nav",
        )

        st.divider()

        # Quick stats in sidebar
        st.markdown("**Portfolio Snapshot**")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total", stats.get("total", "—"))
            st.metric("🔴 Critical", stats.get("critical_count", "—"))
        with col2:
            st.metric("Avg Score", f'{stats.get("avg_overall_score", 0):.1f}')
            st.metric("⚠️ Unacked", stats.get("unacknowledged_alert_count", "—"))

        st.divider()

        # Risk distribution mini bar
        if suppliers and len(suppliers) > 0:
            st.markdown("**Risk Distribution**")
            level_counts = Counter(s["risk_level"] for s in suppliers)
            total = len(suppliers)
            for level, color in [
                ("CRITICAL", "#dc2626"),
                ("HIGH", "#ea580c"),
                ("MEDIUM", "#ca8a04"),
                ("LOW", "#16a34a"),
            ]:
                count_val = level_counts.get(level, 0)
                pct = (count_val / total) * 100
                bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
                st.markdown(
                    f'<div style="font-size:0.75rem;margin:0.15rem 0;">'
                    f'<span style="color:{color};font-weight:600;">{level}</span> '
                    f'<span style="color:#888888;">{bar} {count_val}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        st.divider()
        if st.button("🔄  Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.rerun()

        st.caption("Data from in-process FastAPI backend via ASGITransport")

    return page


# ═══════════════════════════════════════════════════════════════════════════
#  PAGES
# ═══════════════════════════════════════════════════════════════════════════

def render_portfolio():
    st.title("📊 Portfolio Overview")
    st.markdown(
        f'<p style="color:#a0a0a0;margin-top:-0.5rem;">'
        f'Risk assessment across all suppliers — '
        f'<strong>last updated</strong> {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}'
        f'</p>',
        unsafe_allow_html=True,
    )

    stats = get_stats()
    suppliers = get_suppliers()

    # ── KPI Row ──
    total = stats.get("total", 0)
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.markdown(
            f'<div class="kpi-card"><div class="label">Total Suppliers</div>'
            f'<div class="value">{total}</div></div>',
            unsafe_allow_html=True,
        )
    with k2:
        avg_score = stats.get("avg_overall_score", 0)
        st.markdown(
            f'<div class="kpi-card"><div class="label">Avg Risk Score</div>'
            f'<div class="value" style="color:{score_color(avg_score)}">{avg_score:.1f}</div>'
            f'<div class="sub">0 (safe) — 100 (risky)</div></div>',
            unsafe_allow_html=True,
        )
    with k3:
        critical = stats.get("critical_count", 0)
        st.markdown(
            f'<div class="kpi-card"><div class="label">🔴 Critical</div>'
            f'<div class="value" style="color:#dc2626">{critical}</div>'
            f'<div class="sub">{(critical/total*100) if total > 0 else 0:.0f}% of portfolio</div></div>',
            unsafe_allow_html=True,
        )
    with k4:
        high = stats.get("high_count", 0)
        st.markdown(
            f'<div class="kpi-card"><div class="label">🟡 High Risk</div>'
            f'<div class="value" style="color:#ea580c">{high}</div>'
            f'<div class="sub">{(high/total*100) if total > 0 else 0:.0f}% of portfolio</div></div>',
            unsafe_allow_html=True,
        )
    with k5:
        unacked = stats.get("unacknowledged_alert_count", 0)
        st.markdown(
            f'<div class="kpi-card"><div class="label">⚠️ Unacknowledged</div>'
            f'<div class="value" style="color:{"#dc2626" if unacked > 0 else "#16a34a"}">{unacked}</div>'
            f'<div class="sub">alerts requiring action</div></div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Charts Row ──
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.subheader("Risk Level Distribution")
        if suppliers:
            levels = Counter(s["risk_level"] for s in suppliers)
            order = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
            colors_map = {"CRITICAL": "#dc2626", "HIGH": "#ea580c", "MEDIUM": "#ca8a04", "LOW": "#16a34a"}
            chart_data = [{"Risk Level": lv, "Count": levels.get(lv, 0), "Color": colors_map[lv]} for lv in order if levels.get(lv, 0) > 0]

            if chart_data:
                chart_df = pd.DataFrame(chart_data)
                chart = alt.Chart(chart_df).mark_bar(
                    cornerRadiusTopLeft=4,
                    cornerRadiusTopRight=4,
                    size=40,
                ).encode(
                    x=alt.X("Risk Level:N", sort=[lv for lv in order if levels.get(lv, 0) > 0], axis=alt.Axis(labelAngle=0)),
                    y=alt.Y("Count:Q", scale=alt.Scale(domain=[0, max(d["Count"] for d in chart_data) + 1])),
                    color=alt.Color("Risk Level:N", scale=alt.Scale(range=list(colors_map.values())), legend=None),
                    tooltip=["Risk Level:N", "Count:Q"],
                ).properties(
                    height=320,
                )
                st.altair_chart(chart, width='stretch')

            # Keep for the legend below
            counts = [levels.get(lv, 0) for lv in order]
            colors = ["#dc2626", "#ea580c", "#ca8a04", "#16a34a"]

            col_l, col_r = st.columns(2)
            with col_l:
                for level, count, color in zip(order, counts, colors):
                    st.markdown(
                        f'<span style="display:inline-block;width:12px;height:12px;'
                        f'background:{color};border-radius:3px;margin-right:6px;"></span>'
                        f'<strong>{level}</strong> — {count} suppliers',
                        unsafe_allow_html=True,
                    )
            with col_r:
                st.metric("Portfolio Health Index",
                          f"{sum(1 for s in suppliers if s['risk_level'] in ('LOW', 'MEDIUM'))}/{total}",
                          help="Suppliers at LOW or MEDIUM risk")

    with col_chart2:
        st.subheader("Score Distribution by Dimension")
        if suppliers:
            dims = ["financial_score", "operational_score", "compliance_score",
                    "geo_score", "esg_score", "overall_score"]
            dim_labels = ["Financial", "Operational", "Compliance", "Geo", "ESG", "Overall"]
            dist_data = []
            for s in suppliers:
                for dim, label in zip(dims, dim_labels):
                    dist_data.append({"Supplier": s["name"], "Dimension": label, "Score": s.get(dim, 0)})
            df = pd.DataFrame(dist_data)

            chart = st.bar_chart(
                df.pivot_table(index="Dimension", values="Score", aggfunc="mean"),
                height=320,
            )

            avg_scores = {label: sum(s.get(dim, 0) for s in suppliers) / len(suppliers)
                         for dim, label in zip(dims, dim_labels)}
            worst_dim = min(avg_scores, key=avg_scores.get)
            best_dim = max(avg_scores, key=avg_scores.get)
            st.info(
                f"📊 **Best dimension:** {best_dim} ({avg_scores[best_dim]:.1f}) &nbsp;·&nbsp; "
                f"**Worst dimension:** {worst_dim} ({avg_scores[worst_dim]:.1f})"
            )

    st.divider()

    # ── Supplier Table ──
    st.subheader("All Suppliers")
    if suppliers:
        rows = []
        for s in suppliers:
            rows.append({
                "Name": s["name"],
                "Country": s.get("country", ""),
                "Risk Level": risk_badge_html(s["risk_level"]),
                "Score": f"{s.get('overall_score', 0):.1f}",
                "Trend": f'{trend_arrow(s.get("trend", ""))} {s.get("trend", "")}',
                "Alerts": len(s.get("alerts", [])),
                "Last Scanned": s.get("last_scanned_at", "")[:10] if s.get("last_scanned_at") else "",
            })

        df = pd.DataFrame(rows)

        st.markdown(
            df.to_html(escape=False, index=False, classes="data-table"),
            unsafe_allow_html=True,
        )

    # ── Seed Supplier Highlights ──
    st.divider()
    st.subheader("🏷️ Seed Supplier Profiles")

    col_s1, col_s2, col_s3 = st.columns(3)

    # Find seed suppliers
    gt = next((s for s in suppliers if "GlobalTech" in s["name"]), None)
    rc = next((s for s in suppliers if "Reliable" in s["name"]), None)
    acme = next((s for s in suppliers if "Acme" in s["name"]), None)

    with col_s1:
        if gt:
            st.markdown(
                f'<div class="kpi-card">'
                f'<div style="font-weight:600;font-size:1rem;">{gt["name"]}</div>'
                f'<div style="font-size:0.75rem;color:#888888;margin:0.2rem 0 0.5rem;">'
                f'{gt["country"]} · {gt.get("industry", "")}</div>'
                f'{risk_badge_html(gt["risk_level"])} '
                f'<span class="trend-up">🔺 {gt["trend"]}</span>'
                f'<div style="margin-top:0.5rem;">'
                f'<span style="color:#dc2626;font-weight:700;font-size:1.3rem;">{gt["overall_score"]:.1f}</span>'
                f'<span style="color:#888888;font-size:0.8rem;"> / 100</span>'
                f'</div>'
                f'<div style="font-size:0.75rem;color:#a0a0a0;margin-top:0.3rem;">'
                f'🔴 {len(gt["alerts"])} active alerts</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    with col_s2:
        if rc:
            st.markdown(
                f'<div class="kpi-card">'
                f'<div style="font-weight:600;font-size:1rem;">{rc["name"]}</div>'
                f'<div style="font-size:0.75rem;color:#888888;margin:0.2rem 0 0.5rem;">'
                f'{rc["country"]} · {rc.get("industry", "")}</div>'
                f'{risk_badge_html(rc["risk_level"])} '
                f'<span class="trend-flat">➖ {rc["trend"]}</span>'
                f'<div style="margin-top:0.5rem;">'
                f'<span style="color:#16a34a;font-weight:700;font-size:1.3rem;">{rc["overall_score"]:.1f}</span>'
                f'<span style="color:#888888;font-size:0.8rem;"> / 100</span>'
                f'</div>'
                f'<div style="font-size:0.75rem;color:#a0a0a0;margin-top:0.3rem;">'
                f'✅ No alerts</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    with col_s3:
        if acme:
            st.markdown(
                f'<div class="kpi-card">'
                f'<div style="font-weight:600;font-size:1rem;">{acme["name"]}</div>'
                f'<div style="font-size:0.75rem;color:#888888;margin:0.2rem 0 0.5rem;">'
                f'{acme["country"]} · {acme.get("industry", "")}</div>'
                f'{risk_badge_html(acme["risk_level"])} '
                f'<span class="trend-up">🔺 {acme["trend"]}</span>'
                f'<div style="margin-top:0.5rem;">'
                f'<span style="color:#ea580c;font-weight:700;font-size:1.3rem;">{acme["overall_score"]:.1f}</span>'
                f'<span style="color:#888888;font-size:0.8rem;"> / 100</span>'
                f'</div>'
                f'<div style="font-size:0.75rem;color:#a0a0a0;margin-top:0.3rem;">'
                f'🟡 {len(acme["alerts"])} alerts</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


def render_suppliers():
    st.title("🏢 Supplier Detail View")
    st.markdown(
        f'<p style="color:#a0a0a0;margin-top:-0.5rem;">'
        f'Select a supplier to view detailed risk scores, history trends, and alerts.'
        f'</p>',
        unsafe_allow_html=True,
    )

    suppliers = get_suppliers()
    if not suppliers:
        st.warning("No supplier data available.")
        return

    # ── Supplier Selector ──
    names = [s["name"] for s in suppliers]
    selected_name = st.selectbox("Choose a supplier:", names, index=0)
    selected = next(s for s in suppliers if s["name"] == selected_name)
    detail = get_supplier_detail(selected["supplier_id"]) or selected

    # ── Supplier Header ──
    col_h1, col_h2, col_h3 = st.columns([2, 1, 1])
    with col_h1:
        st.markdown(
            f'<h2 style="margin:0;">{detail["name"]}</h2>'
            f'<p style="color:#a0a0a0;margin:0;">{detail.get("country", "")} · '
            f'{detail.get("industry", "")}</p>',
            unsafe_allow_html=True,
        )
    with col_h2:
        st.markdown(
            f'<div style="text-align:center;padding:0.5rem;">'
            f'<div style="font-size:0.75rem;color:#a0a0a0;text-transform:uppercase;">Risk Level</div>'
            f'<div style="font-size:1.5rem;font-weight:700;color:{score_color(detail["overall_score"])};">'
            f'{risk_badge_html(detail["risk_level"])}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with col_h3:
        st.markdown(
            f'<div style="text-align:center;padding:0.5rem;">'
            f'<div style="font-size:0.75rem;color:#a0a0a0;text-transform:uppercase;">Trend</div>'
            f'<div style="font-size:1.5rem;">{trend_arrow(detail["trend"])}</div>'
            f'<div style="font-weight:600;">{detail["trend"]}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Score Gauges ──
    st.subheader("Dimension Scores")
    dims = [
        ("Financial", detail.get("financial_score", 0)),
        ("Operational", detail.get("operational_score", 0)),
        ("Compliance", detail.get("compliance_score", 0)),
        ("Geopolitical", detail.get("geo_score", 0)),
        ("ESG", detail.get("esg_score", 0)),
    ]

    cols = st.columns(5)
    for i, (label, score) in enumerate(dims):
        with cols[i]:
            color = score_color(score)
            # Visual gauge using HTML
            pct = score / 100.0
            fill_color = color
            bg_color = "#333333"

            st.markdown(
                f'<div style="text-align:center;">'
                f'<div style="font-size:0.75rem;font-weight:500;color:#a0a0a0;text-transform:uppercase;'
                f'margin-bottom:0.3rem;">{label}</div>'
                f'<div style="position:relative;width:100%;height:8px;background:{bg_color};'
                f'border-radius:4px;overflow:hidden;margin-bottom:0.3rem;">'
                f'<div style="width:{pct*100}%;height:100%;background:{fill_color};'
                f'border-radius:4px;transition:width 0.5s;"></div>'
                f'</div>'
                f'<div style="font-size:1.3rem;font-weight:700;color:{fill_color};">{score:.1f}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ── Overall Score Highlight ──
    overall = detail.get("overall_score", 0)
    st.markdown(
        f'<div style="text-align:center;padding:1rem;background:#1a1a1a;border-radius:12px;'
        f'border:1px solid #333;margin:0.5rem 0;">'
        f'<div style="font-size:0.8rem;color:#a0a0a0;text-transform:uppercase;letter-spacing:0.04em;">'
        f'Overall Risk Score</div>'
        f'<div style="font-size:2.5rem;font-weight:700;color:{score_color(overall)};">{overall:.1f}'
        f'<span style="font-size:1rem;color:#888888;font-weight:400;"> / 100</span></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.divider()

    # ── History Chart ──
    history = detail.get("history", [])
    if history:
        st.subheader("30-Day Score History")
        hist_df = pd.DataFrame({
            "Day": list(range(1, len(history) + 1)),
            "Score": history,
        })
        st.line_chart(hist_df.set_index("Day"), height=280)

        # Mini stats
        min_score = min(history)
        max_score = max(history)
        current = history[-1]
        change = current - history[0]
        change_str = f"+{change:.1f}" if change > 0 else f"{change:.1f}"
        change_color = "#dc2626" if change > 0 else "#16a34a"

        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        col_s1.metric("Start", f"{history[0]:.1f}")
        col_s2.metric("End", f"{current:.1f}")
        col_s3.metric("Change", change_str,
                      delta_color="inverse" if change > 0 else "normal")
        col_s4.metric("Range", f"{min_score:.1f} — {max_score:.1f}")

    st.divider()

    # ── Alerts for this Supplier ──
    alerts = detail.get("alerts", [])
    if alerts:
        st.subheader(f"🔔 Alerts ({len(alerts)})")
        for alert in alerts:
            sev = alert.get("severity", "HIGH")
            acked = alert.get("acknowledged", False)
            card_class = f"alert-card {sev.lower()} {'acked' if acked else ''}"
            st.markdown(
                f'<div class="{card_class}">'
                f'<div style="display:flex;justify-content:space-between;align-items:flex-start;">'
                f'<div>'
                f'<strong>{alert.get("title", "")}</strong>'
                f'<div style="font-size:0.85rem;color:#cccccc;margin-top:0.2rem;">'
                f'{alert.get("message", "")}</div>'
                f'</div>'
                f'<div style="text-align:right;flex-shrink:0;">'
                f'{risk_badge_html(sev)}'
                f'<div style="font-size:0.7rem;color:#888888;margin-top:0.2rem;">'
                f'{"✅ Acknowledged" if acked else "⏳ Pending"}</div>'
                f'</div>'
                f'</div>'
                f'<div style="font-size:0.8rem;color:#a0a0a0;margin-top:0.5rem;">'
                f'💡 {alert.get("recommendations", [None])[0] if alert.get("recommendations") else ""}'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.success("✅ No alerts for this supplier.")


def render_alerts():
    st.title("🔔 Alerts Center")
    st.markdown(
        f'<p style="color:#a0a0a0;margin-top:-0.5rem;">'
        f'Manage and review all risk alerts across your supplier portfolio.'
        f'</p>',
        unsafe_allow_html=True,
    )

    suppliers = get_suppliers()

    # ── Filters ──
    col_f1, col_f2, col_f3, col_f4 = st.columns([1.5, 1.5, 2, 1])
    with col_f1:
        severity_filter = st.selectbox("Severity", ["ALL", "CRITICAL", "HIGH"], key="alerts_sev")
    with col_f2:
        ack_filter = st.selectbox("Status", ["ALL", "Unacknowledged", "Acknowledged"], key="alerts_ack")
    with col_f3:
        sup_opts = ["ALL"] + [s["name"] for s in suppliers]
        sup_filter = st.selectbox("Supplier", sup_opts, key="alerts_sup")
    with col_f4:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Apply", use_container_width=True):
            st.rerun()

    # ── Fetch with filters ──
    sev_param = severity_filter if severity_filter != "ALL" else None
    ack_param = {"Unacknowledged": False, "Acknowledged": True}.get(ack_filter) if ack_filter != "ALL" else None
    sup_id_param = next(
        (s["supplier_id"] for s in suppliers if s["name"] == sup_filter), None
    ) if sup_filter != "ALL" else None

    alerts = get_alerts(severity=sev_param, acknowledged=ack_param, supplier_id=sup_id_param)

    # ── Summary bar ──
    if alerts:
        critical_count = sum(1 for a in alerts if a.get("severity") == "CRITICAL")
        high_count = sum(1 for a in alerts if a.get("severity") == "HIGH")
        unacked_count = sum(1 for a in alerts if not a.get("acknowledged", False))

        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        col_s1.metric("Total Alerts", len(alerts))
        col_s2.metric("🔴 Critical", critical_count)
        col_s3.metric("🟡 High", high_count)
        col_s4.metric("⏳ Unacknowledged", unacked_count)

        st.divider()

        # ── Bulk Action ──
        unacked_alerts = [a for a in alerts if not a.get("acknowledged", False)]
        if unacked_alerts and st.button(
            f"✅ Acknowledge All ({len(unacked_alerts)} unacknowledged)",
            use_container_width=True,
            type="primary",
        ):
            ids = [a["alert_id"] for a in unacked_alerts]
            status, result = bulk_acknowledge(ids)
            if status == 200:
                st.success(f"✅ Acknowledged {result.get('acknowledged_count', len(ids))} alerts!")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error(f"Failed: {result}")

        st.divider()

        # ── Alert Cards ──
        for alert in alerts:
            sev = alert.get("severity", "HIGH")
            acked = alert.get("acknowledged", False)
            card_class = f"alert-card {sev.lower()} {'acked' if acked else ''}"

            with st.container():
                st.markdown(
                    f'<div class="{card_class}">'
                    f'<div style="display:flex;justify-content:space-between;align-items:flex-start;">'
                    f'<div style="flex:1;">'
                    f'<div style="display:flex;align-items:center;gap:0.5rem;flex-wrap:wrap;">'
                    f'<strong>{alert.get("title", "")}</strong>'
                    f'{risk_badge_html(sev)}'
                    f'</div>'
                    f'<div style="font-size:0.8rem;color:#888888;margin-top:0.15rem;">'
                    f'{alert.get("supplier_name", "")} · '
                    f'{alert.get("dimension", "")} · '
                    f'{alert.get("created_at", "")[:16].replace("T", " ")}'
                    f'</div>'
                    f'<div style="font-size:0.85rem;color:#cccccc;margin-top:0.3rem;">'
                    f'{alert.get("message", "")}</div>'
                    f'<div style="font-size:0.8rem;color:#a0a0a0;margin-top:0.4rem;">'
                    f'💡 <strong>Recommendations:</strong></div>'
                    f'<ul style="font-size:0.8rem;color:#a0a0a0;margin:0.1rem 0 0 1.2rem;padding:0;">'
                    + "".join(
                        f'<li>{rec}</li>'
                        for rec in alert.get("recommendations", [])
                    ) +
                    f'</ul>'
                    f'</div>'
                    f'<div style="text-align:right;flex-shrink:0;min-width:100px;">'
                    f'<div style="font-size:0.7rem;color:#888888;margin-bottom:0.3rem;">'
                    f'{"✅ Acknowledged" if acked else "⏳ Pending"}</div>'

                    f'</div>'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # Actual Streamlit acknowledge button (works)
                if not acked:
                    btn_key = f"ack_{alert['alert_id']}"
                    if st.button(f"✅ Acknowledge", key=btn_key, use_container_width=False):
                        status, _ = acknowledge_alert(alert["alert_id"])
                        if status == 200:
                            st.success(f"Acknowledged: {alert.get('title', '')}")
                            st.cache_data.clear()
                            st.rerun()

                st.markdown("<br>", unsafe_allow_html=True)
    else:
        st.info("ℹ️ No alerts match the current filters.")


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    page = render_sidebar()

    # Page routing
    if "Portfolio" in page:
        render_portfolio()
    elif "Suppliers" in page:
        render_suppliers()
    elif "Alerts" in page:
        render_alerts()

    # Footer
    st.markdown(
        '<div class="footer">'
        'Supplier Risk Scan Dashboard &bull; '
        f'Built with Streamlit + FastAPI + ASGITransport &bull; '
        f'{datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")} UTC'
        '</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
