import streamlit as st

from modules.ai_ops import analyze_logs, build_incident_report, build_operational_summary, build_predictive_signal
from modules.data_sources import get_data_source, render_data_source_sidebar
from modules.settings import init_session_settings
from modules.ui import inject_global_css

st.set_page_config(page_title="AI Ops", page_icon="🤖", layout="wide")
inject_global_css()
init_session_settings()
data_source = get_data_source()
devices_df = data_source.get_devices()
traffic_df = data_source.get_traffic_history(hours=24)
live_device_names = devices_df["name"].astype(str).tolist() if "name" in devices_df.columns else []
default_live_device = live_device_names[0] if live_device_names else "Gateway/Router"

st.markdown('<div class="page-header"><h2>AI Operations Center</h2></div>', unsafe_allow_html=True)
st.caption("AI-powered incident response for diagnosis, command execution guidance, root-cause analysis, and rapid operator action.")

st.markdown("""
<div style="background: linear-gradient(90deg, #0f172a 0%, #1e3a8a 100%); padding: 16px 18px; border-radius: 12px; color: white; margin-bottom: 16px;">
<strong>Mission control for network incidents</strong><br>
Use this workspace to triage alerts, identify likely causes, collect the right vendor commands, and move from detection to action quickly.
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("**Telemetry source**")
    render_data_source_sidebar()
    st.divider()
    st.markdown("**Diagnostic context**")
    st.session_state.setdefault("ai_device_name", default_live_device)
    st.session_state.setdefault("ai_alert_metric", "latency_ms")
    st.session_state.setdefault("ai_alert_message", "High latency and packet loss detected")
    st.session_state.setdefault("ai_log_text", "")
    st.session_state.setdefault("ai_incident_id", "INC-001")
    st.session_state.setdefault("ai_location", "Core network")
    st.session_state.setdefault("ai_owner", "Network Operations")
    st.session_state.setdefault("ai_platform", "Cisco IOS")
    st.session_state.setdefault("ai_impact_scope", "Users in one site")

    template_options = {
        "Latency incident": {"device": "Router-Core-01", "metric": "latency_ms", "message": "High latency and packet loss detected", "logs": "interface ethernet link flap detected"},
        "Routing issue": {"device": "Router-Core-01", "metric": "route_flaps", "message": "OSPF neighbor down", "logs": "ospf neighbor adjacency reset"},
        "DHCP failure": {"device": "Switch-Access-01", "metric": "dhcp_leases", "message": "DHCP pool exhausted", "logs": "dhcp lease pool exhausted"},
        "Link flap": {"device": "Switch-Access-02", "metric": "interface_errors", "message": "Interface flapping", "logs": "interface ethernet crc errors"},
    }
    template_name = st.selectbox("Incident template", list(template_options.keys()))
    if st.button("Load template"):
        preset = template_options[template_name]
        st.session_state.ai_device_name = preset["device"]
        st.session_state.ai_alert_metric = preset["metric"]
        st.session_state.ai_alert_message = preset["message"]
        st.session_state.ai_log_text = preset["logs"]
        st.session_state.pop("ai_plan", None)

    st.divider()
    incident_id = st.text_input("Incident ID", key="ai_incident_id")
    if live_device_names:
        live_target = st.selectbox("Live telemetry target", live_device_names, key="ai_live_target")
        if st.button("Use live target for diagnosis"):
            st.session_state.ai_device_name = live_target
            st.session_state.pop("ai_plan", None)
            st.rerun()
    device_name = st.text_input("Device name", key="ai_device_name")
    platform = st.selectbox("Device platform", ["Cisco IOS", "MikroTik RouterOS", "Linux", "Other"], key="ai_platform")
    location = st.text_input("Location / service", key="ai_location")
    owner = st.text_input("Incident owner", key="ai_owner")
    impact_scope = st.selectbox(
        "Business impact scope",
        ["Users in one site", "Multiple sites", "Critical service", "No user impact confirmed"],
        key="ai_impact_scope",
    )
    alert_metric = st.text_input("Alert metric", key="ai_alert_metric")
    alert_message = st.text_area("Alert message", key="ai_alert_message")
    log_text = st.text_area("Recent logs / paste event output", key="ai_log_text", height=220)
    st.caption("Tip: paste interface errors, routing drops, or DHCP failures to improve the diagnosis.")

analysis = analyze_logs(log_text, device_name=device_name) if log_text.strip() else None

matching_devices = devices_df[devices_df["name"].astype(str).str.casefold() == device_name.strip().casefold()] if "name" in devices_df.columns else devices_df.iloc[0:0]
selected_device = matching_devices.iloc[0] if not matching_devices.empty else None

left, right = st.columns([1.25, 0.75])
with left:
    st.markdown("### Incident workspace")
    context_cols = st.columns(3)
    context_cols[0].metric("Incident", incident_id)
    context_cols[1].metric("Platform", platform)
    context_cols[2].metric("Impact", impact_scope)
    st.caption(f"Owner: {owner} · Scope: {location}")

    if selected_device is not None:
        telemetry_cols = st.columns(4)
        telemetry_cols[0].metric("Device state", str(selected_device.get("status", "unknown")).upper())
        telemetry_cols[1].metric("Latency", f"{float(selected_device.get('latency_ms', 0) or 0):.1f} ms")
        telemetry_cols[2].metric("Packet loss", f"{float(selected_device.get('packet_loss_pct', 0) or 0):.1f}%")
        telemetry_cols[3].metric("CPU", f"{float(selected_device.get('cpu_usage', 0) or 0):.1f}%")
    else:
        st.warning("No current telemetry matches this device name. The diagnosis will use the supplied alert and logs.")

    if st.button("Generate AI diagnosis", type="primary"):
        alert = {
            "id": incident_id,
            "device": device_name,
            "metric": alert_metric,
            "message": alert_message,
            "platform": platform,
            "location": location,
            "owner": owner,
            "impact_scope": impact_scope,
        }
        summary = build_operational_summary(alert, logs=log_text, devices_df=devices_df, traffic_df=traffic_df)
        st.session_state.ai_plan = summary

    if "ai_plan" in st.session_state:
        plan = st.session_state.ai_plan
        severity_color = "🔴" if plan.get("severity") == "critical" else "🟠"
        st.markdown(f"### {severity_color} Incident Summary")
        st.info(plan["likely_cause"])

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.markdown("**Severity**")
            st.write(plan.get("severity", "warning").upper())
        with col_b:
            st.markdown("**Priority**")
            st.write(plan.get("priority", "P2"))
        with col_c:
            st.markdown("**Impact**")
            st.write(plan.get("impact", "Service degradation is possible."))

        st.markdown("**First action**")
        st.write(plan.get("recommended_action", "Isolate the affected path and validate the current state."))
        st.write(plan["summary"])

        st.markdown("### Operator checks")
        for item in plan.get("operator_checks", []):
            st.write(f"- {item}")

        st.markdown("### Recommended next steps")
        for item in plan.get("next_steps", []):
            st.write(f"- {item}")

        if plan.get("evidence_tags"):
            st.markdown("### Evidence tags")
            st.write(", ".join(plan["evidence_tags"]))

        if plan.get("telemetry_notes"):
            st.markdown("### Telemetry notes")
            for note in plan["telemetry_notes"]:
                st.write(f"- {note}")

        signal = build_predictive_signal(devices_df, traffic_df, device_name=device_name)
        st.markdown("### Predictive risk")
        st.metric(label="Risk level", value=signal["status"].upper(), delta=f"score {signal['score']}")
        st.write(signal["summary"])

        if plan.get("commands"):
            st.markdown("### Ready-to-use commands")
            for item in plan["commands"]:
                st.markdown(f"**{item['platform']}**")
                st.code(item["command"])
                st.caption(item["purpose"])

        st.markdown("### Incident report")
        report_text = build_incident_report(
            plan,
            root_cause=analysis["root_cause"] if analysis else None,
        )
        st.text_area("Copy / export preview", report_text, height=220)
        st.download_button(
            label="Download report",
            data=report_text,
            file_name="incident_report.txt",
            mime="text/plain",
        )

with right:
    st.markdown("### Root-cause intelligence")
    if analysis:
        st.write(analysis["root_cause"])
        st.caption(f"Confidence: {analysis['confidence']:.0%}")
        if analysis.get("evidence"):
            st.write("Evidence:")
            for item in analysis["evidence"]:
                st.write(f"- {item}")
    else:
        st.info("Paste logs to trigger root-cause detection.")

    st.divider()
    st.markdown("### Why this section matters")
    st.write("This panel is designed to help an engineer move from suspicion to action quickly with a clear incident summary, operator checks, and precise vendor commands.")
