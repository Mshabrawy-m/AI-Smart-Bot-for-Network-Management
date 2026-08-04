# AI Smart Bot for Network Management System

Streamlit web app for network administrators: a RAG chatbot, live and simulated telemetry, alerting, diagnostics, AI Ops workflows, and a network monitor.

## Features

- AI-powered incident diagnosis, root-cause analysis, and remediation guidance
- Cisco and MikroTik troubleshooting commands
- Live or simulated telemetry for safe demos and testing
- Network checks: ICMP ping, HTTP, DNS, port scanning, and traceroute
- Dashboard alerts, forecasting, anomaly detection, reports, and a knowledge-base chatbot

## Run locally

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
streamlit run app.py
```

Add an LLM API key to your local `.streamlit/secrets.toml`:

```toml
LLM_PROVIDER = "groq"
GROQ_API_KEY = "your-key"

# Or use Gemini:
# LLM_PROVIDER = "gemini"
# GEMINI_API_KEY = "your-key"
```

Never commit `secrets.toml` or share API keys in source code, documentation, or chat.

## Deploy to Streamlit Community Cloud

1. Create a GitHub repository and push this project with `app.py` at the repository root.
2. At [share.streamlit.io](https://share.streamlit.io), create an app from the GitHub repository and choose `app.py` as the main file.
3. Open **App settings → Secrets** and add only the provider you plan to use:

   ```toml
   LLM_PROVIDER = "groq"
   GROQ_API_KEY = "your-key"
   # Or: LLM_PROVIDER = "gemini" and GEMINI_API_KEY = "your-key"
   ```

4. Optional: configure the public live-monitoring targets:

   ```toml
   MONITORED_HOSTS = "8.8.8.8, 1.1.1.1, example.com"
   ```

5. Deploy. Future pushes to GitHub redeploy the app automatically.

## Important deployment note

Streamlit Community Cloud cannot normally reach private LAN devices such as `192.168.x.x` or `10.x.x.x`. For real LAN monitoring, deploy on a machine inside the network, use a VPN, or implement a local collector. Simulated mode remains available for a safe demonstration.

## Project structure

```text
app.py                  # Home page
pages/                  # Chatbot, Dashboard, Monitor, AI Ops
modules/                # Monitoring, LLM, RAG, alerts, reports, storage
data/knowledge_base.json
.streamlit/             # Theme configuration and local secrets template
```

## License

Graduation project — adjust as needed for your institution.
