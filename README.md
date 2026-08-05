# AI Smart Bot for Network Management System

> **Graduation Project** — An AI-powered network operations dashboard that monitors infrastructure, detects anomalies with ML, and diagnoses faults using natural language via LLM APIs.

**Live Demo:** [ai-smart-bot-for-network-management.streamlit.app](https://ai-smart-bot-for-network-management.streamlit.app)

---

## Features

| Feature | Description |
|---------|-------------|
| **AI Chatbot** | Two modes: RAG-only (fast, KB-grounded) and Agent (tool-calling with live data). Ask networking questions or paste diagnostics for interpretation. |
| **NOC Dashboard** | Real-time device metrics, threshold-based alerts with AI explanations, 24-hour traffic forecasting with confidence intervals, incident management with approval workflows. |
| **Network Monitor** | Live ICMP ping, HTTP health checks, DNS lookups, port scanning with security assessment, batch monitoring, traceroute, and a multi-host analysis dashboard. |
| **AI Ops Suite** | Fault diagnosis, ML anomaly detection (RF+GB ensemble), log root-cause analysis, capacity forecasting, human-in-the-loop remediation, AI-generated reports. |
| **Diagnostics Bridge** | When a fault is detected (device down, high latency, packet loss spike), the alert is sent to the LLM, which returns a plain-language explanation with numbered troubleshooting steps — including Cisco/MikroTik commands. |

---

## Architecture

```
┌──────────────────────── Streamlit UI (4 pages) ────────────────────────┐
│   Home  ·  Chatbot  ·  Dashboard  ·  Network Monitor  ·  AI Ops        │
└──────────────────────────────┬─────────────────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                      ▼
 ┌──────────────┐     ┌──────────────┐      ┌────────────────┐
 │ data_sources  │     │  llm_client  │      │ network_monitor│
 │ (live/real/   │     │(Groq/Gemini) │      │(ICMP/HTTP/DNS/ │
 │  simulated)   │     │              │      │ port scanning) │
 └──────┬───────┘     └──────┬───────┘      └───────┬────────┘
        │                    │                       │
        └────────────────────┼───────────────────────┘
                             ▼
              ┌──────────────────────────────┐
              │       Core Modules           │
              │  alerts · anomaly_detector   │
              │  chatbot · agent · forecast  │
              │  diagnostics_bridge          │
              │  knowledge_base · remediation│
              │  reports · storage · ui      │
              └──────────────┬───────────────┘
                             │
                      ┌──────┴──────┐
                      ▼             ▼
                network_bot.db   session_state
                (SQLite WAL)     (in-memory)
```

### Alert → Explanation flow

1. `data_sources.py` collects device metrics (live ping + psutil, 30-day CSV, or simulated)
2. `alerts.py` evaluates thresholds → alert objects (critical / warning / ok)
3. User clicks **Explain** on an alert
4. `diagnostics_bridge.py` searches the knowledge base → builds structured prompt → calls LLM
5. Explanation (cause + numbered steps) is displayed inline
6. Event is logged to SQLite with retrieval score and latency

### Agent chatbot flow

1. User query → `agent.py` calls Groq with 5 tool definitions (function-calling)
2. Model decides which tools to invoke (max 4 iterations):
   - `search_knowledge_base` — TF-IDF search over 40 networking entries
   - `check_device_status` — live device metrics
   - `run_ping` — real ICMP probe
   - `get_recent_alerts` — current threshold alerts
   - `get_anomaly_score` — RF+GB ensemble prediction
3. Tool results are fed back as context → final answer with collapsible tool trace

---

## Tech Stack

| Category | Technology |
|----------|------------|
| **Framework** | Python 3.12 · Streamlit ≥1.32 |
| **LLM (primary)** | Groq API (`openai/gpt-oss-120b`) via `groq` SDK |
| **LLM (fallback)** | Google Gemini (`gemini-2.0-flash`) via `google-generativeai` |
| **ML — Anomaly** | scikit-learn · RandomForest + GradientBoosting ensemble (300 trees each) with auto-labeling |
| **ML — Forecast** | statsmodels (Holt-Winters) · scikit-learn (Linear Regression) · rolling average — auto-selected |
| **ML — RAG** | TF-IDF vectorization + cosine similarity over local JSON knowledge base |
| **Charts** | Plotly (graph_objects) — bar, line, radar, dual-axis with threshold overlays |
| **Network** | ping3 (ICMP) · socket (TCP fallback, DNS) · requests (HTTP) · psutil (host metrics) |
| **Storage** | SQLite (WAL mode) — chat history, alerts, incidents, evaluation metrics |
| **i18n** | English + Arabic (RTL) via settings module |

---

## Project Structure

```
├── app.py                            # Home page, sidebar, navigation
├── requirements.txt                  # Python dependencies
├── runtime.txt                       # Python 3.12 version spec
├── network_bot.db                    # SQLite database (auto-created)
│
├── .streamlit/
│   ├── config.toml                   # Dark NOC theme
│   ├── secrets.toml                  # API keys (git-ignored, never commit)
│   └── secrets.toml.example          # Template — safe to commit
│
├── data/
│   ├── knowledge_base.json           # 40 networking Q&A entries for RAG
│   └── real_network_traffic.csv      # 30-day traffic data (5-min intervals)
│
├── modules/
│   ├── __init__.py                   # Python 3.14 import workaround
│   ├── llm_client.py                 # Groq / Gemini wrapper with fallback
│   ├── knowledge_base.py             # TF-IDF search engine with LRU cache
│   ├── chatbot.py                    # RAG orchestration: retrieve → prompt → LLM
│   ├── agent.py                      # Agentic chatbot with 5-tool function-calling
│   ├── data_sources.py               # Live / Real CSV / Simulated data adapters
│   ├── network_monitor.py            # ICMP ping, HTTP, DNS, port scanner, traceroute
│   ├── alerts.py                     # Threshold-based alert engine
│   ├── diagnostics_bridge.py         # Alert → KB context → LLM explanation
│   ├── anomaly_detector.py           # RF+GB ensemble with auto-labeling
│   ├── forecasting.py                # Holt-Winters / Linear / Rolling forecasting
│   ├── remediation.py                # Human-in-the-loop incident state machine
│   ├── reports.py                    # AI-generated health and incident reports
│   ├── settings.py                   # Thresholds, i18n (EN + AR), provider config
│   ├── storage.py                    # SQLite persistence (chat, alerts, incidents, eval)
│   └── ui.py                         # Global CSS injection (NOC dark theme)
│
├── pages/
│   ├── 1_Chatbot.py                  # Chat UI — RAG mode + Agent tool-calling mode
│   ├── 2_Dashboard.py                # Device KPIs, alert feed, charts, forecast, incidents
│   ├── 3_Network_Monitor.py          # Ping, HTTP, DNS, port scan, batch, traceroute, analysis
│   └── 4_AI_Ops.py                   # Fault diagnosis, anomaly ML, log analysis, remediation
│
├── tests/
│   └── test_ai_workflows.py          # Unit tests for core AI workflows
│
└── dev/                              # Development & benchmark scripts
    ├── bench_deep.py                 # Deep learning model comparison
    ├── bench_models.py               # Anomaly detection model benchmark
    ├── eval_accuracy.py              # Full accuracy evaluation (ML + forecast)
    ├── feature_performance.py        # Knowledge base and alert perf tests
    ├── run_sanity_checks.py          # Core module smoke tests
    └── tune_threshold.py             # Decision threshold calibration
```

---

## Setup (Local)

### Prerequisites

- **Python 3.12** (required — Python 3.14 has import compatibility issues)
- **Groq API key** (free) — [console.groq.com](https://console.groq.com)
- *(Optional)* Gemini API key — [aistudio.google.com](https://aistudio.google.com)

### Install & Run

```bash
# Clone and enter directory
git clone https://github.com/Mshabrawy-m/AI-Smart-Bot-for-Network-Management.git
cd AI-Smart-Bot-for-Network-Management

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

# Install dependencies
pip install -r requirements.txt

# Configure API keys
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
# Edit .streamlit/secrets.toml with your API keys

# Run
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501).

### Secrets configuration

```toml
# .streamlit/secrets.toml
LLM_PROVIDER = "groq"
GROQ_API_KEY = "gsk_your_key_here"

# Optional fallback provider:
# LLM_PROVIDER = "gemini"
# GEMINI_API_KEY = "your_gemini_key_here"

# Optional: override monitored hosts for live mode
# MONITORED_HOSTS = "192.168.1.1, 10.0.0.1, 8.8.8.8"
```

> **Never commit `secrets.toml`.** It is already in `.gitignore`.

---

## Deploy to Streamlit Community Cloud

1. Push this repo to GitHub with `app.py` at the root.
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app** → select repo → main file `app.py`.
3. In **Settings → Advanced**, set **Python version to 3.12** (required — Cloud ignores `runtime.txt`).
4. In **Settings → Secrets**, add your API keys:
   ```toml
   LLM_PROVIDER = "groq"
   GROQ_API_KEY = "gsk_your_key_here"
   ```
5. Click **Deploy**. Every push redeploys automatically.

### Deployment limitations

Streamlit Cloud **cannot reach private LAN addresses** (`192.168.x.x`, `10.x.x.x`). Live mode pings public hosts (Google DNS, Cloudflare, etc.) but not your internal router. For real LAN monitoring, deploy on-premises or use a VPN. Simulated mode works identically everywhere.

---

## Machine Learning

### Anomaly Detection (`modules/anomaly_detector.py`)

- **Algorithm:** Supervised ensemble — RandomForest (300 trees) + GradientBoosting (300 trees) with soft voting
- **Auto-labeling:** Domain rules generate training labels without manual annotation:
  - Contextual spikes (>k × rolling standard deviation)
  - Global IQR outlier gates
  - Sudden change detection
  - Hard thresholds per metric (packet_loss > 3%, latency > 150ms, CPU > 90%)
- **Features:** Rolling mean/std/z-score (24-period window), rate-of-change, time features (hour, day_of_week, business_hour, peak_hour)
- **Decision:** Threshold 0.65 with Z-score safety gate (4.0σ) for extreme outliers
- **Output:** Anomaly score (0–1) + per-feature contributions

### Forecasting (`modules/forecasting.py`)

- **Three methods** auto-selected by data characteristics:
  - **Exponential Smoothing** (Holt-Winters with damped trend) — for strong trends
  - **Linear Regression** — for moderate trends
  - **Rolling Average** — for high variance or insufficient data
- **Output:** Predicted value + 95% confidence interval
- **Use:** Dashboard warns when forecast exceeds capacity threshold within 30-minute horizon

### Knowledge Base / RAG (`modules/knowledge_base.py`)

- **Content:** 40 networking entries covering OSI, TCP/IP, DNS, DHCP, VLAN, routing, switching, firewalls, VPN, SNMP, BGP, OSPF, load balancing, and more
- **Indexing:** TF-IDF vectorization over `topic + keywords + answer` text
- **Retrieval:** Cosine similarity with LRU cache (128 entries)
- **Evaluation:** Logs retrieval score, hit/miss, and latency per query

---

## Results

**What this system does** — monitors live/real/simulated network infrastructure (ICMP, HTTP, DNS, port scan, traceroute), classifies device/metric states with an ML anomaly detector, forecasts traffic capacity, and explains alerts / answers questions through a Groq/Gemini LLM agent with retrieval-augmented grounding and human-in-the-loop remediation.

**Tools used:** scikit-learn (RandomForest + GradientBoosting ensemble, TF-IDF retrieval), statsmodels (Holt-Winters), Groq & Gemini LLM APIs, Streamlit UI, SQLite (WAL) persistence, `ping3`/`requests`/`socket`/`psutil`.

### Anomaly Detection (classification) — RF + GB Ensemble

Evaluated on `data/real_network_traffic.csv` (8,640 rows, 5-min intervals; 80/20 split → 6,287 normal / 625 anomalies auto-labeled in training). Ground truth = same domain rules used for auto-labeling; metrics computed on the held-out 20% test set.

| Metric | Value |
|---|---|
| Precision | 0.993 |
| Recall | 0.993 |
| F1 Score | 0.993 |
| False Positive Rate | 0.0006 |
| True positives / false negatives | 146 / 1 |
| False alarms | 1 |
| Test anomalies | 147 / 1,728 (8.5%) |

### Time Series Forecasting — 30-min horizon (walk-forward, n = 354 windows)

| Metric | MAE | MAPE | RMSE | Model selected |
|---|---|---|---|---|
| bandwidth_mbps | 20.99 | 34.6% | 39.66 | Exponential smoothing (Holt-Winters, damped trend) |
| latency_ms | 8.05 | 19.8% | 19.73 | Rolling average |
| packet_loss_pct | 0.11 | N/A* | 0.54 | Exponential smoothing |

\* MAPE is undefined for near-zero packet-loss values; MAE is the reliable metric there.

Reproduce all of the above with `python dev/eval_accuracy.py`.

---

## APIs & Services

| Service | Purpose | Access |
|---------|---------|--------|
| **Groq** | Primary LLM (`openai/gpt-oss-120b`) | Free tier, API key in secrets |
| **Google Gemini** | Fallback LLM (`gemini-2.0-flash`) | Free tier, API key in secrets |
| **ping3** | ICMP latency & reachability | Local library, no key |
| **psutil** | Host CPU, memory, network I/O | Local library, no key |
| **requests** | HTTP health checks | Standard library |
| **socket** | DNS lookups, TCP probes | Standard library |

No external monitoring SaaS, no cloud database, no paid infrastructure required.

---

## Known Limitations

| Constraint | Detail |
|-----------|--------|
| **No local LLM** | Hosted APIs only (Groq/Gemini). Requires internet + API key. |
| **API rate limits** | Free tiers have daily/RPM quotas. Swap providers via `LLM_PROVIDER` in secrets. |
| **Session state** | Resets on restart. Only SQLite-persisted data (incidents, eval metrics) survives. |
| **SNMP stubbed** | Extension point only. Wire to `pysnmp` for production use. |
| **Agent latency** | 2–5s per tool call, up to 4 iterations per query. |
| **ICMP privileges** | Raw sockets may require admin. Falls back to TCP probing (ports 443/80). |
| **TF-IDF vs embeddings** | Fast and free but misses semantic similarity. Upgrade path: embedding vector store. |
| **Python 3.14** | Has import machinery incompatibilities on Streamlit Cloud. Use Python 3.12. |

---

## Language Support

The UI supports **English** and **Arabic**. Toggle in the sidebar. Arabic text renders RTL via CSS. All labels, captions, and section headers have translations in `modules/settings.py`.

---

## Evaluation Hooks

Every chatbot query and alert explanation is logged to `network_bot.db` with:
- Retrieval score (TF-IDF cosine similarity of top KB hit)
- Retrieval hit/miss flag
- End-to-end latency (ms)
- Provider and temperature

This enables reporting retrieval hit-rate and answer latency from real interactions during the graduation demo.

---

## Testing

```bash
pytest tests/test_ai_workflows.py -v
```

Tests cover: anomaly detection outlier accuracy, alert explanation with mocked LLM, operational summary generation, predictive signal building, incident report structure, remediation lifecycle (create → diagnose → suggest → approve), and report fallback when LLM fails.

---

## References

### Large Language Models & AI Agents

| # | Reference |
|---|----------|
| [1] | Groq Inc. — *GroqCloud LPU Inference Engine*. [https://groq.com](https://groq.com) |
| [2] | Google DeepMind — *Gemini: A Family of Highly Capable Multimodal Models*, 2024. [arxiv.org/abs/2312.11805](https://arxiv.org/abs/2312.11805) |
| [3] | Liu, C., Xie, X., Zhang, X., & Cui, Y. — *Large Language Models for Networking: Workflow, Advances and Challenges*, 2024. [arxiv.org/abs/2404.12901](https://arxiv.org/abs/2404.12901) |
| [4] | OpenAI — *Function Calling with Chat Completions API*. [platform.openai.com/docs/guides/function-calling](https://platform.openai.com/docs/guides/function-calling) |
| [5] | Wei, J. et al. — *Chain-of-Thought Prompting Elicits Reasoning in Large Language Models*, NeurIPS 2022. [arxiv.org/abs/2201.11903](https://arxiv.org/abs/2201.11903) |
| [6] | Yao, S. et al. — *ReAct: Synergizing Reasoning and Acting in Language Models*, ICLR 2023. [arxiv.org/abs/2210.03629](https://arxiv.org/abs/2210.03629) |
| [7] | Schick, T. et al. — *Toolformer: Language Models Can Teach Themselves to Use Tools*, NeurIPS 2023. [arxiv.org/abs/2302.04761](https://arxiv.org/abs/2302.04761) |

### Retrieval-Augmented Generation (RAG)

| # | Reference |
|---|----------|
| [8] | Lewis, P. et al. — *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*, NeurIPS 2020. [arxiv.org/abs/2005.11401](https://arxiv.org/abs/2005.11401) |
| [9] | Gao, Y. et al. — *Retrieval-Augmented Generation for Large Language Models: A Survey*, 2024. [arxiv.org/abs/2312.10997](https://arxiv.org/abs/2312.10997) |
| [10] | Salton, G. & Buckley, C. — *Term-Weighting Approaches in Automatic Text Retrieval*, Information Processing & Management, 1988. [doi.org/10.1016/0306-4573(88)90021-0](https://doi.org/10.1016/0306-4573(88)90021-0) |
| [11] | Manning, C. et al. — *Introduction to Information Retrieval*, Cambridge University Press, 2008. [nlp.stanford.edu/IR-book](https://nlp.stanford.edu/IR-book/) |

### Machine Learning — Anomaly Detection

| # | Reference |
|---|----------|
| [12] | Breiman, L. — *Random Forests*, Machine Learning 45(1), 2001. [doi.org/10.1023/A:1010933404324](https://doi.org/10.1023/A:1010933404324) |
| [13] | Friedman, J. H. — *Greedy Function Approximation: A Gradient Boosting Machine*, Annals of Statistics, 2001. [doi.org/10.1214/aos/1013203451](https://doi.org/10.1214/aos/1013203451) |
| [14] | Bharathi, I. & Makhija, R. — *Network Intrusion Detection System using Random Forest and Gradient Boosting Machines*, 2024. [doi.org/10.1109/CONIT61985.2024.10627542](https://doi.org/10.1109/CONIT61985.2024.10627542) |
| [15] | Chandola, V. et al. — *Anomaly Detection: A Survey*, ACM Computing Surveys 41(3), 2009. [doi.org/10.1145/1541880.1541882](https://doi.org/10.1145/1541880.1541882) |
| [16] | Pedregosa, F. et al. — *Scikit-learn: Machine Learning in Python*, JMLR 12, 2011. [jmlr.org/papers/v12/pedregosa11a.html](https://jmlr.org/papers/v12/pedregosa11a.html) |
| [17] | Dietterich, T. G. — *Ensemble Methods in Machine Learning*, MCS 2000. [doi.org/10.1007/3-540-45014-9_1](https://doi.org/10.1007/3-540-45014-9_1) |

### Time Series Forecasting

| # | Reference |
|---|----------|
| [18] | Hyndman, R. J. & Athanasopoulos, G. — *Forecasting: Principles and Practice*, 3rd ed., OTexts, 2021. [otexts.com/fpp3](https://otexts.com/fpp3/) |
| [19] | Holt, C. C. — *Forecasting Seasonals and Trends by Exponentially Weighted Moving Averages*, International Journal of Forecasting, 2004. [doi.org/10.1016/j.ijforecast.2003.09.015](https://doi.org/10.1016/j.ijforecast.2003.09.015) |
| [20] | Winters, P. R. — *Forecasting Sales by Exponentially Weighted Moving Averages*, Management Science, 1960. [doi.org/10.1287/mnsc.6.3.324](https://doi.org/10.1287/mnsc.6.3.324) |
| [21] | Hyndman, R. J., Koehler, A. B., Ord, J. K., & Snyder, R. D. — *Forecasting with Exponential Smoothing: The State Space Approach*, Springer Series in Statistics, 2008. [doi.org/10.1007/978-3-540-71918-2](https://doi.org/10.1007/978-3-540-71918-2) |

### Network Management & Monitoring

| # | Reference |
|---|----------|
| [22] | Stallings, W. — *Data and Computer Communications*, 10th ed., Pearson, 2014. |
| [23] | Kurose, J. F. & Ross, K. W. — *Computer Networking: A Top-Down Approach*, 8th ed., Pearson, 2021. [gaia.cs.umass.edu/kurose_ross](https://gaia.cs.umass.edu/kurose_ross/) |
| [24] | RFC 792 — *Internet Control Message Protocol (ICMP)*. [rfc-editor.org/rfc/rfc792](https://www.rfc-editor.org/rfc/rfc792) |
| [25] | RFC 3411–3418 — *SNMPv3 Architecture*. [rfc-editor.org/rfc/rfc3411](https://www.rfc-editor.org/rfc/rfc3411) |
| [26] | Cisco — *Network Management Best Practices*. [cisco.com/c/en/us/support/docs/network-management](https://www.cisco.com) |
| [27] | Subramanian, M. — *Network Management: Principles and Practice*, 2nd ed., Pearson, 2010. |

### Frameworks & Libraries

| # | Reference |
|---|----------|
| [28] | Streamlit Inc. — *Streamlit Documentation*. [docs.streamlit.io](https://docs.streamlit.io) |
| [29] | Plotly Technologies Inc. — *Plotly Python Graphing Library*. [plotly.com/python](https://plotly.com/python/) |
| [30] | Giannakakis, G. — *psutil: A Cross-Platform Library for System and Process Utilities*. [github.com/giampaolo/psutil](https://github.com/giampaolo/psutil) |
| [31] | SQLite Consortium — *SQLite: The Database Engine*. [sqlite.org](https://www.sqlite.org) |
| [32] | Streamlit Community Cloud — *Deploy Streamlit Apps*. [share.streamlit.io](https://share.streamlit.io) |

### AIOps & Intelligent IT Operations

| # | Reference |
|---|----------|
| [33] | Gartner — *Market Guide for AIOps Platforms*, 2022. [gartner.com/en/documents/4016379](https://www.gartner.com/en/documents/4016379) |
| [34] | Bhattacharjee, A. et al. — *AIOps: Intelligent IT Operations for Cloud and Network Management*, IEEE, 2022. [doi.org/10.1109/ACCESS.2022.3187250](https://doi.org/10.1109/ACCESS.2022.3187250) |
| [35] | Dang, Y. et al. — *AI in Operations Management: Applications and Challenges*, Production and Operations Management, 2022. [doi.org/10.1111/poms.13676](https://doi.org/10.1111/poms.13676) |

### Information Retrieval (Lexical Models)

| # | Reference |
|---|----------|
| [36] | Robertson, S. E. & Zaragoza, H. — *The Probabilistic Relevance Framework: BM25 and Beyond*, Foundations and Trends® in Information Retrieval, 2009. [doi.org/10.1561/1500000019](https://doi.org/10.1561/1500000019) |

### AI-Driven Log Analysis & Human-in-the-Loop Remediation

| # | Reference |
|---|----------|
| [37] | Liu, Y., Tao, S., Meng, W., Wang, J., Ma, W., Zhao, Y., Chen, Y., Yang, H., Jiang, Y., & Chen, X. — *Interpretable Online Log Analysis Using Large Language Models with Prompt Strategies (LogPrompt)*, Proc. ICPC 2024, 2023. [arxiv.org/abs/2308.07610](https://arxiv.org/abs/2308.07610) |
| [38] | Wittkopp, T., Wiesner, P., & Kao, O. — *LogRCA: Log-based Root Cause Analysis for Distributed Services*, Euro-Par 2024, 2024. [arxiv.org/abs/2405.13599](https://arxiv.org/abs/2405.13599) |
| [39] | Mukherjee, S. — *AI-Driven Autonomous IT Operations: A Human-in-the-Loop AIOps 2.0 Framework*, Int. J. Intell. Syst. Appl. Eng., 12(23s), 4317–4325, 2024. [doi.org/10.17762/ijisae.v12i23s.8304](https://doi.org/10.17762/ijisae.v12i23s.8304) |

### Project Reference

| # | Reference |
|---|----------|
| [40] | *AI Smart Bot for Network Management System* (graduation project, 2026). GitHub. [github.com/Mshabrawy-m/AI-Smart-Bot-for-Network-Management](https://github.com/Mshabrawy-m/AI-Smart-Bot-for-Network-Management) |

---

## License

Graduation project — adjust attribution and license terms as required by your institution.
