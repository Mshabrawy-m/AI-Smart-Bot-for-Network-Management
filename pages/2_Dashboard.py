"""Network Dashboard — NOC-style ops view with tabs, forecasting, and incident management."""

from __future__ import annotations

import json
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.alerts import generate_alerts, alert_summary
from modules.diagnostics_bridge import explain_alert
from modules.llm_client import LLMConfigurationError
from modules.data_sources import get_data_source, render_data_source_sidebar
from modules.forecasting import NetworkForecaster
from modules.settings import get_text, init_session_settings
from modules.storage import save_alert, get_history, get_evaluation_metrics
from modules.ui import inject_global_css
from modules.remediation import get_remediation_engine
from modules.reports import get_report_generator

st.set_page_config(page_title="Dashboard", page_icon="📡", layout="wide")
inject_global_css()
init_session_settings()

# ── Extra CSS for dashboard-specific density ──────────────────────────────────
st.markdown("""
<style>
.kpi-label { font-family: 'IBM Plex Mono', monospace; font-size: 0.72rem;
             color: #94A3B8; text-transform: uppercase; letter-spacing: 0.06em; }
.kpi-value { font-family: 'IBM Plex Mono', monospace; font-size: 1.6rem;
             font-weight: 600; line-height: 1.1; }
.kpi-up    { color: #22C55E; }
.kpi-warn  { color: #F59E0B; }
.kpi-crit  { color: #EF4444; }
.kpi-neutral { color: #E2E8F0; }
.device-row { font-family: 'IBM Plex Mono', monospace; font-size: 0.82rem;
              padding: 0.3rem 0; border-bottom: 1px solid #1E293B; }
.section-rule { border: none; border-top: 1px solid #334155; margin: 1rem 0; }
.forecast-card { background: #1E293B; border: 1px solid #334155;
                 border-radius: 3px; padding: 0.6rem 0.9rem; margin-bottom: 0.5rem; }
.incident-row { background: #1E293B; border-left: 3px solid #F59E0B;
                padding: 0.6rem 0.9rem; margin-bottom: 0.6rem; }
.incident-row.critical { border-left-color: #EF4444; }
.incident-row.approved  { border-left-color: #22C55E; }
.incident-row.rejected  { border-left-color: #475569; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar — thresholds + refresh ───────────────────────────────────────────
with st.sidebar:
    st.markdown('<span class="kpi-label">Alert Thresholds</span>', unsafe_allow_html=True)
    cpu_threshold = st.slider("CPU Warning (%)", 50, 100,
        int(st.session_state.thresholds.get("cpu_warning", 85)), step=5)
    pkt_threshold = st.slider("Packet Loss (%)", 0.5, 10.0,
        float(st.session_state.thresholds.get("packet_loss_warning", 1.5)), step=0.5)
    lat_threshold = st.slider("Latency Warning (ms)", 50, 500,
        int(st.session_state.thresholds.get("latency_warning_ms", 100)), step=10)

    st.session_state.thresholds = {
        "cpu_warning": float(cpu_threshold),
        "packet_loss_warning": float(pkt_threshold),
        "latency_warning_ms": float(lat_threshold),
    }

    st.divider()
    if st.button("↺  Refresh telemetry", use_container_width=True):
        for key in ("devices_df", "traffic_df", "alert_explanations", "forecast_cache"):
            st.session_state.pop(key, None)
        st.rerun()

    st.divider()
    st.markdown('<span class="kpi-label">Data source</span>', unsafe_allow_html=True)
    render_data_source_sidebar()

# ── Data loading (cached in session for the page lifetime) ────────────────────
data_source = get_data_source()

if "devices_df" not in st.session_state:
    st.session_state.devices_df = data_source.get_devices()
if "traffic_df" not in st.session_state:
    st.session_state.traffic_df = data_source.get_traffic_history(hours=24)
if "alert_explanations" not in st.session_state:
    st.session_state.alert_explanations = {}

devices_df: pd.DataFrame = st.session_state.devices_df
traffic_df: pd.DataFrame = st.session_state.traffic_df
alerts = generate_alerts(devices_df, thresholds=st.session_state.thresholds)
summary = alert_summary(alerts)

# ── Derived KPIs ──────────────────────────────────────────────────────────────
up_count   = int((devices_df["status"] == "up").sum())
down_count = int((devices_df["status"] == "down").sum())
total      = len(devices_df)
up_pct     = (up_count / total * 100) if total else 0.0
avg_cpu    = devices_df.loc[devices_df["status"] == "up", "cpu_usage"].mean()
avg_lat    = devices_df.loc[devices_df["status"] == "up", "latency_ms"].mean()
crit_count = summary["critical"]
warn_count = summary["warning"]

# Availability colour
avail_cls = "kpi-up" if up_pct >= 95 else ("kpi-warn" if up_pct >= 80 else "kpi-crit")
alert_cls = "kpi-crit" if crit_count else ("kpi-warn" if warn_count else "kpi-up")

# ── Page header + KPI strip ───────────────────────────────────────────────────
st.markdown(f'<div class="page-header"><h2>{get_text("dashboard_title")}</h2></div>', unsafe_allow_html=True)
st.caption(get_text("dashboard_caption"))

k1, k2, k3, k4, k5, k6 = st.columns(6)

def _kpi(col, label: str, value: str, css_class: str = "kpi-neutral") -> None:
    col.markdown(
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value {css_class}">{value}</div>',
        unsafe_allow_html=True,
    )

_kpi(k1, "Availability",    f"{up_pct:.1f}%",                            avail_cls)
_kpi(k2, "Devices up",      f"{up_count}/{total}",                       "kpi-up" if down_count == 0 else "kpi-warn")
_kpi(k3, "Devices down",    str(down_count),                             "kpi-crit" if down_count else "kpi-neutral")
_kpi(k4, "Active alerts",   f"{crit_count}C / {warn_count}W",           alert_cls)
_kpi(k5, "Avg CPU",         f"{avg_cpu:.1f}%" if pd.notna(avg_cpu) else "—",
     "kpi-warn" if pd.notna(avg_cpu) and avg_cpu > cpu_threshold else "kpi-neutral")
_kpi(k6, "Avg latency",     f"{avg_lat:.0f} ms" if pd.notna(avg_lat) else "—",
     "kpi-warn" if pd.notna(avg_lat) and avg_lat > lat_threshold else "kpi-neutral")

st.markdown('<hr class="section-rule">', unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_overview, tab_devices, tab_traffic, tab_incidents, tab_report = st.tabs([
    "Overview",
    "Devices",
    "Traffic & Forecast",
    "Incident Management",
    "Report",
])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — OVERVIEW: alerts + host metrics
# ═══════════════════════════════════════════════════════════════════════════════
with tab_overview:
    left, right = st.columns([3, 2])

    with left:
        st.markdown('<span class="kpi-label">Alert Feed</span>', unsafe_allow_html=True)
        actionable = [a for a in alerts if a["level"] != "ok"]
        display_alerts = actionable if actionable else alerts

        for idx, alert in enumerate(display_alerts):
            level = alert["level"]
            css  = level if level in ("critical", "warning") else "ok"
            dot_cls = f"status-{level}" if level in ("critical","warning") else "status-ok"

            st.markdown(
                f'<div class="alert-feed {css}">'
                f'<span class="mono {dot_cls}">● {level.upper()}</span>&nbsp;&nbsp;'
                f'{alert["message"]}'
                f"</div>",
                unsafe_allow_html=True,
            )

            btn_key = f"explain_{idx}_{alert['device']}_{alert['metric']}"
            if st.button("Explain →", key=btn_key, help="Get AI diagnosis for this alert"):
                with st.spinner("Generating diagnosis…"):
                    try:
                        explanation = explain_alert(alert)
                        st.session_state.alert_explanations[btn_key] = explanation
                        save_alert(alert, explanation)
                    except LLMConfigurationError as exc:
                        st.session_state.alert_explanations[btn_key] = f"⚠ {exc}"
                    except Exception as exc:
                        st.session_state.alert_explanations[btn_key] = f"Error: {exc}"

            if btn_key in st.session_state.alert_explanations:
                st.info(st.session_state.alert_explanations[btn_key])

    with right:
        st.markdown('<span class="kpi-label">Host Metrics (this machine)</span>', unsafe_allow_html=True)
        try:
            host = data_source.get_host_metrics()
            hc1, hc2, hc3 = st.columns(3)
            hc1.metric("CPU", f"{host.get('cpu_percent', 0):.1f}%")
            hc2.metric("Memory", f"{host.get('memory_percent', 0):.1f}%")
            hc3.metric("Net I/O", f"{host.get('network_throughput_mbps', 0):.1f} Mbps")
            if host.get("error"):
                st.caption(f"Note: {host['error']}")
        except Exception as exc:
            st.caption(f"Host metrics unavailable: {exc}")

        st.markdown('<hr class="section-rule">', unsafe_allow_html=True)
        st.markdown('<span class="kpi-label">Alert History</span>', unsafe_allow_html=True)
        try:
            history_data = get_history(limit=20)
            past_alerts = history_data.get("alerts", [])
            if past_alerts:
                for ev in past_alerts[:8]:
                    try:
                        ad = json.loads(ev["alert_json"])
                        lvl = ad.get("level","warning")
                        st.markdown(
                            f'<div class="alert-feed {lvl}" style="margin-bottom:0.3rem;">'
                            f'<span class="mono" style="font-size:0.7rem;">{ev["created_at"][:16]}</span>'
                            f'&nbsp;<span class="mono status-{lvl}">● {lvl.upper()}</span>'
                            f'&nbsp;{ad.get("message","")[:60]}'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    except Exception:
                        continue
            else:
                st.caption("No alert history yet.")
        except Exception as exc:
            st.caption(f"Could not load history: {exc}")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — DEVICES: full table + per-device bar charts
# ═══════════════════════════════════════════════════════════════════════════════
with tab_devices:
    st.markdown('<span class="kpi-label">Device Inventory</span>', unsafe_allow_html=True)

    # Render compact table — works for both Simulated (8 cols) and Live (9 cols with 'host')
    display_df = devices_df.copy()
    display_df["cpu_usage"]       = display_df["cpu_usage"].apply(lambda v: f"{v:.1f}%")
    display_df["latency_ms"]      = display_df["latency_ms"].apply(lambda v: f"{v:.1f} ms")
    display_df["packet_loss_pct"] = display_df["packet_loss_pct"].apply(lambda v: f"{v:.2f}%")
    display_df["bandwidth_mbps"]  = display_df["bandwidth_mbps"].apply(lambda v: f"{v:.0f} Mbps")
    display_df["uptime_pct"]      = display_df["uptime_pct"].apply(lambda v: f"{v:.1f}%")
    display_df = display_df.rename(columns={
        "name": "Name", "host": "Host", "type": "Type", "status": "Status",
        "cpu_usage": "CPU", "latency_ms": "Latency", "packet_loss_pct": "Pkt Loss",
        "bandwidth_mbps": "Bandwidth", "uptime_pct": "Uptime",
    })
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    st.markdown('<hr class="section-rule">', unsafe_allow_html=True)
    st.markdown('<span class="kpi-label">Per-device metrics</span>', unsafe_allow_html=True)

    bc1, bc2 = st.columns(2)
    raw = st.session_state.devices_df  # use raw numeric df for charts

    with bc1:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=raw["name"], y=raw["cpu_usage"],
            marker_color=[
                "#EF4444" if v >= cpu_threshold else "#F59E0B" if v >= cpu_threshold * 0.75 else "#22C55E"
                for v in raw["cpu_usage"]
            ],
            name="CPU %",
        ))
        fig.update_layout(
            title="CPU Usage (%)", yaxis_range=[0, 100],
            plot_bgcolor="#0F172A", paper_bgcolor="#0F172A",
            font_color="#94A3B8", margin=dict(t=36, b=0, l=0, r=0),
            xaxis_tickangle=-30,
        )
        st.plotly_chart(fig, use_container_width=True)

    with bc2:
        lat_df = raw.dropna(subset=["latency_ms"])
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            x=lat_df["name"], y=lat_df["latency_ms"],
            marker_color=[
                "#EF4444" if v >= lat_threshold else "#F59E0B" if v >= lat_threshold * 0.75 else "#22C55E"
                for v in lat_df["latency_ms"]
            ],
            name="Latency ms",
        ))
        fig2.update_layout(
            title="Latency (ms)",
            plot_bgcolor="#0F172A", paper_bgcolor="#0F172A",
            font_color="#94A3B8", margin=dict(t=36, b=0, l=0, r=0),
            xaxis_tickangle=-30,
        )
        st.plotly_chart(fig2, use_container_width=True)

    fig3 = go.Figure()
    fig3.add_trace(go.Bar(
        x=raw["name"], y=raw["bandwidth_mbps"],
        marker_color="#38BDF8", name="Bandwidth Mbps",
    ))
    fig3.update_layout(
        title="Bandwidth Snapshot (Mbps)",
        plot_bgcolor="#0F172A", paper_bgcolor="#0F172A",
        font_color="#94A3B8", margin=dict(t=36, b=0, l=0, r=0),
        xaxis_tickangle=-30,
    )
    st.plotly_chart(fig3, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — TRAFFIC & FORECAST
# ═══════════════════════════════════════════════════════════════════════════════
with tab_traffic:
    # Forecasting inline KPIs
    forecaster = NetworkForecaster(method="auto")
    fc_bw  = forecaster.forecast_metric(traffic_df, "bandwidth_mbps",  horizon_minutes=30)
    fc_lat = forecaster.forecast_metric(traffic_df, "latency_ms",      horizon_minutes=30)
    fc_pkt = forecaster.forecast_metric(traffic_df, "packet_loss_pct", horizon_minutes=30)

    fc1, fc2, fc3 = st.columns(3)
    def _fc_metric(col, label, forecast_dict, unit="", invert=False):
        v = forecast_dict.get("predicted_value")
        lo = forecast_dict.get("lower_bound")
        hi = forecast_dict.get("upper_bound")
        err = forecast_dict.get("error")
        if err or v is None:
            col.metric(f"30-min forecast — {label}", "n/a", help=err or "insufficient data")
        else:
            col.metric(
                f"30-min forecast — {label}",
                f"{v:.1f}{unit}",
                delta=f"±{(hi - lo) / 2:.1f}{unit} CI",
                delta_color="off",
            )

    _fc_metric(fc1, "Bandwidth",   fc_bw,  " Mbps")
    _fc_metric(fc2, "Latency",     fc_lat, " ms")
    _fc_metric(fc3, "Packet Loss", fc_pkt, "%")

    method_used = fc_bw.get("method_used", "rolling")
    st.caption(f"Forecast method: {method_used} · {fc_bw.get('data_points_used', 0)} data points · 95% CI shown")

    st.markdown('<hr class="section-rule">', unsafe_allow_html=True)

    # 24-hour traffic chart — bandwidth + latency dual axis
    st.markdown('<span class="kpi-label">24-hour traffic history</span>', unsafe_allow_html=True)

    tdf = traffic_df.copy()
    tdf["timestamp"] = pd.to_datetime(tdf["timestamp"])

    fig_traffic = go.Figure()
    fig_traffic.add_trace(go.Scatter(
        x=tdf["timestamp"], y=tdf["bandwidth_mbps"],
        mode="lines", name="Bandwidth (Mbps)",
        line=dict(color="#38BDF8", width=1.5),
        fill="tozeroy", fillcolor="rgba(56,189,248,0.08)",
    ))

    # Add forecast point
    if fc_bw.get("predicted_value") is not None:
        last_ts = tdf["timestamp"].max()
        fut_ts  = last_ts + pd.Timedelta(minutes=30)
        fig_traffic.add_trace(go.Scatter(
            x=[fut_ts], y=[fc_bw["predicted_value"]],
            mode="markers", name="BW forecast (+30 min)",
            marker=dict(color="#F59E0B", size=10, symbol="diamond"),
            error_y=dict(
                type="data",
                symmetric=False,
                array=[fc_bw["upper_bound"] - fc_bw["predicted_value"]],
                arrayminus=[fc_bw["predicted_value"] - fc_bw["lower_bound"]],
                color="#F59E0B",
            ),
        ))

    fig_traffic.add_trace(go.Scatter(
        x=tdf["timestamp"], y=tdf["latency_ms"],
        mode="lines", name="Latency (ms)",
        line=dict(color="#A78BFA", width=1, dash="dot"),
        yaxis="y2",
    ))

    fig_traffic.update_layout(
        plot_bgcolor="#0F172A", paper_bgcolor="#0F172A",
        font_color="#94A3B8",
        legend=dict(orientation="h", y=1.05, bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(gridcolor="#1E293B"),
        yaxis=dict(title=dict(text="Bandwidth (Mbps)", font=dict(color="#38BDF8")),
                   gridcolor="#1E293B"),
        yaxis2=dict(title=dict(text="Latency (ms)", font=dict(color="#A78BFA")),
                    overlaying="y", side="right", gridcolor="rgba(0,0,0,0)"),
        margin=dict(t=20, b=0, l=0, r=0),
        hovermode="x unified",
    )
    st.plotly_chart(fig_traffic, use_container_width=True)

    # Packet loss chart
    st.markdown('<span class="kpi-label">Packet loss %</span>', unsafe_allow_html=True)
    fig_pkt = go.Figure()
    fig_pkt.add_trace(go.Scatter(
        x=tdf["timestamp"], y=tdf["packet_loss_pct"],
        mode="lines", name="Packet loss %",
        line=dict(color="#F87171", width=1),
        fill="tozeroy", fillcolor="rgba(248,113,113,0.08)",
    ))
    fig_pkt.update_layout(
        plot_bgcolor="#0F172A", paper_bgcolor="#0F172A",
        font_color="#94A3B8",
        xaxis=dict(gridcolor="#1E293B"),
        yaxis=dict(title="Packet Loss (%)", gridcolor="#1E293B"),
        margin=dict(t=10, b=0, l=0, r=0),
        showlegend=False,
    )
    st.plotly_chart(fig_pkt, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — INCIDENT MANAGEMENT (Remediation approvals + create incident)
# ═══════════════════════════════════════════════════════════════════════════════
with tab_incidents:
    remediation_engine = get_remediation_engine()
    pending = remediation_engine.get_pending_approvals()
    recent  = remediation_engine.get_incident_history(limit=20)

    # ── Pending approvals (surfaced prominently) ──────────────────────────────
    if pending:
        st.markdown(
            f'<div class="kpi-value kpi-warn" style="font-size:1rem;">'
            f'▲ {len(pending)} pending approval{"s" if len(pending) != 1 else ""}'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.markdown("")
        for incident in pending:
            with st.container():
                st.markdown(
                    f'<div class="incident-row">'
                    f'<span class="mono status-warn">● PENDING APPROVAL</span>&nbsp;&nbsp;'
                    f'<strong>{incident.device}</strong> — {incident.issue_type}'
                    f'&nbsp;<span class="mono" style="color:#64748B; font-size:0.75rem;">'
                    f'detected {incident.detected_at.strftime("%Y-%m-%d %H:%M")}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if incident.diagnosis:
                    st.caption(f"Diagnosis: {incident.diagnosis[:120]}")
                if incident.suggested_action:
                    act = incident.suggested_action
                    ic1, ic2, ic3 = st.columns(3)
                    ic1.markdown(f'<span class="kpi-label">Proposed action</span><br>'
                                 f'<span class="mono">{act.action_type.value}</span>',
                                 unsafe_allow_html=True)
                    ic2.markdown(f'<span class="kpi-label">Estimated impact</span><br>'
                                 f'<span class="mono">{act.estimated_impact}</span>',
                                 unsafe_allow_html=True)
                    ic3.markdown(f'<span class="kpi-label">Rollback plan</span><br>'
                                 f'<span class="mono">{act.rollback_plan}</span>',
                                 unsafe_allow_html=True)
                    st.caption(f"Severity: {act.severity} · {act.description}")

                ca, cr, _ = st.columns([1, 1, 5])
                if ca.button("Approve", key=f"approve_{incident.incident_id}", type="primary"):
                    remediation_engine.approve_action(incident.incident_id, "Approved via Dashboard")
                    st.rerun()
                if cr.button("Reject", key=f"reject_{incident.incident_id}"):
                    remediation_engine.reject_action(incident.incident_id, "Rejected via Dashboard")
                    st.rerun()
                st.markdown('<hr class="section-rule">', unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="alert-feed ok"><span class="mono status-ok">● No pending approvals</span></div>',
            unsafe_allow_html=True,
        )

    # ── Create incident from current alert ────────────────────────────────────
    st.markdown('<span class="kpi-label">Create incident from alert</span>', unsafe_allow_html=True)
    actionable_alerts = [a for a in alerts if a["level"] != "ok"]
    if actionable_alerts:
        alert_options = {
            f"[{a['level'].upper()}] {a['device']} — {a['metric']}": a
            for a in actionable_alerts
        }
        selected_label = st.selectbox("Select alert", list(alert_options.keys()), key="incident_alert_sel")
        selected_alert = alert_options[selected_label]

        from modules.remediation import RemediationActionType
        action_type = st.selectbox(
            "Proposed action",
            [a.value for a in RemediationActionType],
            key="incident_action_sel",
        )
        severity = st.select_slider("Severity", ["low", "medium", "high"], value="medium", key="incident_sev")

        if st.button("Create & submit for approval", key="create_incident_btn"):
            inc = remediation_engine.create_incident(selected_alert)
            remediation_engine.diagnose_incident(inc.incident_id, selected_alert["message"])
            remediation_engine.suggest_action(
                inc.incident_id,
                RemediationActionType(action_type),
                description=f"Auto-suggested for {selected_alert['device']}",
                severity=severity,
            )
            remediation_engine.submit_for_approval(inc.incident_id)
            st.success(f"Incident created and submitted for approval (ID: {inc.incident_id[:8]}…)")
            st.rerun()
    else:
        st.caption("No active alerts to create incidents from.")

    # ── Incident history ──────────────────────────────────────────────────────
    st.markdown('<hr class="section-rule">', unsafe_allow_html=True)
    st.markdown('<span class="kpi-label">Recent incident history</span>', unsafe_allow_html=True)
    if recent:
        state_color = {
            "approved": "kpi-up", "rejected": "kpi-neutral",
            "pending_approval": "kpi-warn", "detected": "kpi-warn",
            "diagnosed": "kpi-warn", "suggested": "kpi-warn",
        }
        for inc in recent[:15]:
            sc = state_color.get(inc.state.value, "kpi-neutral")
            st.markdown(
                f'<div class="device-row">'
                f'<span class="mono {sc}">{inc.state.value.upper()}</span>&nbsp;&nbsp;'
                f'<strong>{inc.device}</strong> — {inc.issue_type}'
                f'&nbsp;<span style="color:#64748B; font-size:0.75rem;">'
                f'{inc.detected_at.strftime("%m-%d %H:%M")}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.caption("No incidents recorded yet.")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 5 — REPORT
# ═══════════════════════════════════════════════════════════════════════════════
with tab_report:
    st.markdown('<span class="kpi-label">AI-generated network health report</span>', unsafe_allow_html=True)
    st.caption("Pulls current metrics, alerts, and incident log — sends to LLM for a structured markdown report.")

    rc1, rc2 = st.columns(2)
    with rc1:
        time_window = st.slider("Time window (hours)", 1, 168, 24, key="report_time")
    with rc2:
        include_forecasts   = st.checkbox("Include capacity forecast", value=True, key="rpt_fc")

    if st.button("Generate Report", type="primary", key="gen_report_btn"):
        with st.spinner("Generating report…"):
            try:
                rg = get_report_generator()
                report = rg.generate_report(
                    time_window_hours=time_window,
                    include_forecasts=include_forecasts,
                    include_remediation=True,
                )
                st.session_state.generated_report = report
            except LLMConfigurationError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"Report generation failed: {exc}")

    if "generated_report" in st.session_state:
        st.markdown('<hr class="section-rule">', unsafe_allow_html=True)
        st.markdown(st.session_state.generated_report)
        st.download_button(
            label="Download (.md)",
            data=st.session_state.generated_report,
            file_name=f"network_report_{time_window}h.md",
            mime="text/markdown",
        )

    # Evaluation metrics — collapsed, for graduation report reference
    with st.expander("Evaluation metrics (graduation report)", expanded=False):
        try:
            cm = get_evaluation_metrics(event_type="chatbot_query")
            am = get_evaluation_metrics(event_type="alert_explanation")
            agm = get_evaluation_metrics(event_type="agent_query")

            ec1, ec2, ec3 = st.columns(3)
            with ec1:
                st.markdown("**RAG Chatbot**")
                st.metric("Queries", cm["total_events"])
                st.metric("Hit rate", f"{cm['hit_rate']:.2%}")
                if cm["avg_latency_ms"]:
                    st.metric("Avg latency", f"{cm['avg_latency_ms']:.0f} ms")
            with ec2:
                st.markdown("**Alert Explanations**")
                st.metric("Explanations", am["total_events"])
                st.metric("Hit rate", f"{am['hit_rate']:.2%}")
                if am["avg_latency_ms"]:
                    st.metric("Avg latency", f"{am['avg_latency_ms']:.0f} ms")
            with ec3:
                st.markdown("**Agent (tool-calling)**")
                st.metric("Queries", agm["total_events"])
                if agm["avg_latency_ms"]:
                    st.metric("Avg latency", f"{agm['avg_latency_ms']:.0f} ms")
                st.caption("Detailed tool-use metrics are logged in the database.")
        except Exception as exc:
            st.warning(f"Could not load evaluation metrics: {exc}")
