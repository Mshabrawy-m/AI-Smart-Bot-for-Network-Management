"""Shared UI styles — ops-tool aesthetic, applied globally."""

GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
}

h1, h2, h3, h4, h5, h6 {
    font-family: 'IBM Plex Sans', sans-serif;
    font-weight: 600;
    letter-spacing: -0.02em;
}

.mono, .metric-label, .status-line {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.85rem;
}

.status-up { color: #22C55E; }
.status-warn { color: #F59E0B; }
.status-critical { color: #EF4444; }
.status-ok { color: #94A3B8; }

.alert-feed {
    border-left: 3px solid #334155;
    padding: 0.6rem 0.9rem;
    margin-bottom: 0.5rem;
    background: #1E293B;
}

.alert-feed.critical { border-left-color: #EF4444; }
.alert-feed.warning { border-left-color: #F59E0B; }
.alert-feed.ok { border-left-color: #22C55E; }

.page-header {
    border-bottom: 1px solid #334155;
    padding-bottom: 0.75rem;
    margin-bottom: 1.25rem;
}

.constraint-box {
    background: #1E293B;
    border: 1px solid #334155;
    padding: 1rem;
    border-radius: 4px;
    font-size: 0.9rem;
}

.rtl-block {
    direction: rtl;
    text-align: right;
}
</style>
"""


def inject_global_css() -> None:
    import streamlit as st

    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
