# AI Smart Bot for Network Management System — Build Spec

This document is a complete build brief. Feed it to an AI coding assistant
(Claude Code, Cursor, etc.) as the starting instruction, or use it as your
own implementation checklist. It assumes Python + Streamlit + a cloud LLM
API, deployed on Streamlit Community Cloud (free tier).

---

## 1. Project summary

Build a graduation project called **"AI Smart Bot for Network Management
System"**: a Streamlit web app that helps a network administrator monitor
a network and diagnose problems using natural language, powered by an LLM
API + a retrieval-augmented knowledge base.

The app has **three integrated modules**, not three disconnected features:

1. **Chatbot** — answers networking questions and interprets pasted
   diagnostics (ping output, logs, config snippets) using RAG (a local
   knowledge base) + an LLM API for generation.
2. **Dashboard** — visualizes device status, latency, packet loss,
   bandwidth, and CPU usage, with threshold-based alerts.
3. **Network monitor** — performs real ping checks against reachable
   hosts, and (stretch goal) polls real devices via SNMP.

The key differentiator, and the thing that should be emphasized in the
implementation: **the monitor's alerts feed the chatbot.** When the
dashboard detects an anomaly (device down, high latency, packet loss
spike), it should be able to hand that data to the chatbot, which
generates a plain-language diagnosis and suggested next steps. This
"diagnostics bridge" is the core value proposition — build it, don't skip
it in favor of polishing the other two modules.

---

## 2. Constraints to design around (do not ignore these)

- **Streamlit Community Cloud is not inside the developer's LAN.** It can
  reach any public host (ping, HTTP), but not private/internal network
  devices. Real device monitoring only works if: (a) the app is deployed
  on-premise / inside the same network, (b) reached via VPN, or (c) a
  small local agent script pushes data up to the cloud app (e.g. via a
  simple API endpoint or shared database). Default to option where the
  monitor works against public hosts + a documented adapter point for
  real SNMP/device polling later. Don't silently fake "real monitoring."
- **Free LLM API tiers are rate-limited** (requests/day, not unlimited).
  Design the LLM-calling code behind a single wrapper module so the
  provider can be swapped without touching UI code.
- **No persistent storage by default** on Streamlit's free tier —
  session state resets between sessions/restarts. Use SQLite for
  anything that needs to persist (alert history, chat logs) rather than
  assuming an external database is available.
- **Limited compute** — no GPU, modest RAM/CPU. Do NOT run a local LLM
  (no `transformers` + `torch` inference). Use a hosted LLM API instead.

---

## 3. Tech stack

- **Frontend/app framework:** Streamlit (multipage app)
- **LLM API (primary):** Groq API (`groq` Python SDK) — chosen for very
  fast inference and a generous free tier. Model:
  `openai/gpt-oss-120b`. Requires an API key stored as a Streamlit secret
  (`st.secrets["GROQ_API_KEY"]`), never hardcoded, never committed, and
  never pasted into chat/docs/screenshots.
- **LLM API (fallback/alternative):** Google Gemini API — implement as a
  second backend behind the same wrapper interface, selectable via
  config, in case Groq's terms or quota change.
- **RAG / retrieval:** `scikit-learn` TF-IDF + cosine similarity over a
  local JSON knowledge base (no external vector DB needed — keeps it
  free and simple; mention in the report that this could be swapped for
  a proper embedding-based vector store like FAISS or Chroma as future
  work).
- **Networking:** `ping3` for ICMP ping; optional `pysnmp` for SNMP
  polling (stretch goal); `requests` for any HTTP-based checks.
- **Data/viz:** `pandas`, `plotly`.
- **Persistence (optional but recommended):** `sqlite3` (standard
  library) for alert history and chat logs.
- **Secrets management:** `.streamlit/secrets.toml` locally (git-ignored)
  and Streamlit Cloud's "Secrets" panel in production. Never commit API
  keys.

---

## 4. Repository / file structure

```
network_ai_bot/
├── app.py                       # Home page: overview, nav, honest constraints notice
├── requirements.txt
├── .streamlit/
│   ├── config.toml              # theme
│   └── secrets.toml.example     # template, NOT the real secrets file
├── .gitignore                   # must ignore .streamlit/secrets.toml
├── data/
│   └── knowledge_base.json      # networking Q&A / articles for RAG
├── modules/
│   ├── __init__.py
│   ├── llm_client.py            # thin wrapper: get_llm_response(prompt, provider="gemini")
│   ├── knowledge_base.py        # load + TF-IDF search over knowledge_base.json
│   ├── chatbot.py                # RAG orchestration: retrieve -> build prompt -> call llm_client
│   ├── network_monitor.py       # real_ping(), (optional) snmp_poll(), simulate_devices() for demo
│   ├── alerts.py                # threshold logic -> alert objects
│   ├── diagnostics_bridge.py    # alert -> structured prompt -> chatbot -> explanation
│   └── storage.py               # SQLite helpers for chat/alert history (optional module)
├── pages/
│   ├── 1_Chatbot.py
│   ├── 2_Dashboard.py
│   └── 3_Network_Monitor.py
└── README.md                    # setup, run, deploy instructions
```

---

## 5. Module specs

### 5.1 `modules/llm_client.py`
- Export one function: `get_llm_response(messages: list[dict], provider: str = "groq") -> str`.
- `messages` follows the standard `[{"role": "system"|"user"|"assistant", "content": str}]` shape.
- Reads the API key from `st.secrets["GROQ_API_KEY"]` and constructs the
  client as `Groq(api_key=st.secrets["GROQ_API_KEY"])` — do not rely on
  the SDK's implicit `GROQ_API_KEY` env var default in a Streamlit app;
  read it from secrets explicitly. Raise a clear, catchable exception if
  the key is missing (don't crash the whole app — show a friendly
  Streamlit error telling the user to set the secret).
- Groq call shape to implement (non-streaming for simplicity in a
  request/response Streamlit page — streaming is a nice-to-have for the
  chat page later):
  ```python
  from groq import Groq

  def get_llm_response(messages, provider="groq"):
      if provider == "groq":
          client = Groq(api_key=st.secrets["GROQ_API_KEY"])
          completion = client.chat.completions.create(
              model="openai/gpt-oss-120b",
              messages=messages,
              temperature=0.7,
              max_completion_tokens=1024,
              top_p=1,
          )
          return completion.choices[0].message.content
      elif provider == "gemini":
          ...  # fallback implementation
  ```
- Keep `temperature` lower (e.g. 0.3-0.5) for the diagnostics bridge
  (§5.6) where you want consistent, factual troubleshooting steps rather
  than creative variation; a higher value is fine for general chat.
- Stub a `gemini` provider using the same function signature so
  switching providers later is a one-line config change.
- Include basic retry-once-on-failure logic and a timeout.

### 5.2 `modules/knowledge_base.py`
- Load `data/knowledge_base.json` (list of `{id, topic, keywords, answer}` — see §6 for schema).
- Build a TF-IDF matrix over `topic + keywords + answer` at startup.
- Expose `search(query: str, top_k: int = 3) -> list[dict]` returning
  ranked entries with similarity scores.
- Cache the loaded engine with `st.cache_resource` in the calling page,
  not inside the module itself.

### 5.3 `modules/chatbot.py`
- `answer_question(query, history=None) -> dict` with keys
  `{"answer": str, "sources": list[str]}`.
- Flow: retrieve top-2/3 KB entries → build a system+context prompt that
  includes the retrieved snippets → call `llm_client.get_llm_response` →
  return the generated answer plus which KB topics were used (for
  transparency/citations in the UI).
- Handle the "no relevant KB entry" case gracefully — still let the LLM
  attempt a general answer, but flag in the UI that it's not grounded in
  the local knowledge base.

### 5.4 `modules/network_monitor.py`
- `real_ping(host: str, timeout: float = 2.0) -> dict` — real ICMP ping,
  returns status/latency/error/timestamp.
- `simulate_devices(seed=None) -> pandas.DataFrame` — demo device
  inventory (name, type, status, cpu_usage, latency, packet_loss,
  uptime) for the dashboard when no real devices are reachable. Clearly
  document this as simulated in code comments and in the UI.
- Leave a clearly marked extension point / stub function
  `snmp_poll(device_ip, community="public") -> dict` for the SNMP stretch
  goal, even if unimplemented at first — this shows the committee the
  architecture supports real integration.

### 5.5 `modules/alerts.py`
- `generate_alerts(devices_df) -> list[dict]` with `{"level": "critical"|"warning"|"ok", "message": str, "device": str, "metric": str, "value": float}`.
- Threshold rules (make these configurable constants, not magic
  numbers): device down → critical; CPU ≥ 85% → warning; packet loss ≥
  1.5% → warning; latency above a configurable ceiling → warning.

### 5.6 `modules/diagnostics_bridge.py` — the core differentiator
- `explain_alert(alert: dict) -> str`.
- Builds a structured prompt from the alert's device/metric/value data,
  asks the LLM (via `chatbot.py` or directly via `llm_client.py`) to: (1)
  explain the likely cause in plain language, (2) suggest 2-4 concrete
  next troubleshooting steps, (3) note when a step needs the pasted KB
  content vs. general knowledge.
- Called from the Dashboard page: each alert gets an "Explain this 🤖"
  button that calls this function and displays the result inline.

### 5.7 `modules/storage.py` (optional but recommended)
- SQLite helpers: `save_chat_message()`, `save_alert()`, `get_history()`.
- Use a single `network_bot.db` file; create tables on first run if they
  don't exist.

---

## 6. Knowledge base schema (`data/knowledge_base.json`)

```json
[
  {
    "id": "dns",
    "topic": "DNS",
    "keywords": ["dns", "domain name", "resolver"],
    "answer": "Plain-language explanation of DNS, common failure modes, and how to test it."
  }
]
```

Populate with ~20-30 entries covering: OSI model, TCP/IP, subnetting,
DNS, DHCP, VLAN, routing, switching, firewalls, VPN, SNMP, latency vs.
packet loss vs. bandwidth, ping/traceroute usage, Wi-Fi troubleshooting,
common network security threats, and a step-by-step generic
troubleshooting checklist. Write these yourself or with the AI coding
assistant's help — keep each answer concise (3-6 sentences) since it
gets injected into the LLM prompt.

---

## 7. Pages

- **`app.py` (Home):** Project title, three-column summary linking to
  each page, and an explicit "how this works / limitations" expander
  covering the constraints in §2 — this should be visible, not buried,
  since it's part of demonstrating engineering honesty to the committee.
- **`pages/1_Chatbot.py`:** `st.chat_message` UI, sidebar with suggested
  questions, shows which KB topics backed each answer.
- **`pages/2_Dashboard.py`:** Metric cards (devices up/down, avg CPU, avg
  latency), alert list with "Explain this 🤖" buttons wired to
  `diagnostics_bridge.explain_alert`, charts for bandwidth/latency over
  time and per-device CPU, device status table.
- **`pages/3_Network_Monitor.py`:** Text input + quick-pick buttons for
  common public hosts, calls `real_ping`, keeps a session history table.

Support Arabic UI text alongside English if the target audience is
Arabic-speaking — apply a simple RTL CSS class (`direction: rtl;
text-align: right;`) to text blocks; Streamlit itself doesn't need
special config for this.

---

## 8. Environment / secrets

`.streamlit/secrets.toml` (local, git-ignored):
```toml
GROQ_API_KEY = "your-key-here"
LLM_PROVIDER = "groq"
```

**About the key you already generated:** since it was pasted into this
chat, revoke it in the Groq console and generate a fresh one before
putting it in `secrets.toml`. Add `.streamlit/secrets.toml` to
`.gitignore` immediately, before you write anything into it, so it's
never accidentally committed.

On Streamlit Community Cloud: set the same keys under
**App settings → Secrets** in the dashboard — do not commit real keys to
the repository. Commit a `secrets.toml.example` with placeholder values
instead.

---

## 9. Build order (suggested phases for an AI coding assistant to follow)

1. Scaffold the repo structure from §4, empty `app.py` that runs.
2. Implement `llm_client.py` against Groq (`pip install groq`), test with
   a single hardcoded prompt.
3. Write `data/knowledge_base.json` (20-30 entries) and
   `knowledge_base.py` search; test retrieval quality manually.
4. Implement `chatbot.py` combining retrieval + `llm_client`; wire up
   `pages/1_Chatbot.py`.
5. Implement `network_monitor.py` (`real_ping` + `simulate_devices`);
   wire up `pages/3_Network_Monitor.py`.
6. Implement `alerts.py`; wire up `pages/2_Dashboard.py` with charts and
   alert list.
7. Implement `diagnostics_bridge.py` and connect the "Explain this 🤖"
   button on the Dashboard — this is the integration step, test it
   end-to-end with a simulated "device down" alert.
8. (Optional) Add `storage.py` for persistence.
9. (Stretch) Implement `snmp_poll` against a real/virtual lab device.
10. Deploy to Streamlit Community Cloud; verify secrets are configured;
    smoke-test all three pages in production.

---

## 10. Evaluation hooks to build in (for the graduation report)

- Log every chatbot Q&A pair (via `storage.py`) so you can later score
  retrieval hit-rate and answer quality against a manually curated test
  set of ~20-30 questions.
- Log alert → explanation events with timestamps, so you can measure
  detection-to-explanation latency during a fault-injection test (kill a
  monitored host and time the pipeline).

---

## 11. Deployment checklist (Streamlit Community Cloud)

1. Push the repo to GitHub with `app.py` at the root.
2. On share.streamlit.io: New app → select repo/branch → main file
   `app.py`.
3. Add secrets under App settings → Secrets (mirror `secrets.toml`
   format).
4. Deploy; confirm `requirements.txt` installs cleanly (no `torch`/
   `transformers` needed with this architecture — keeps install fast).
5. Every `git push` redeploys automatically.

---

## 12. UI/UX design direction — avoid the generic "AI-generated app" look

Streamlit's default theme, plus the usual AI-coding-tool instincts
(purple/blue gradients, glassmorphism cards, an emoji stapled to every
header, rounded-everything, centered hero text), is instantly
recognizable as templated. This is a network operations tool — it should
look like one. Concretely:

**Reject by default:**
- Purple-to-blue gradient backgrounds or buttons
- Glassmorphism / frosted-glass card panels
- An emoji icon on every single header, metric, and button
- Generic centered "hero" intro text with a big bold title + subtitle +
  three feature cards pattern
- Default Streamlit theme left untouched (the light theme with the
  default red/pink accent, or an unconfigured dark theme)

**Design toward instead — pick one coherent direction and commit to it:**
- **Reference aesthetic:** technical monitoring tools (Grafana, Datadog,
  a NOC display), not a consumer chatbot landing page. Dense, legible,
  information-forward. Whitespace used for grouping, not decoration.
- **Typography:** pick one distinct pairing and set it deliberately via
  custom CSS injected with `st.markdown(..., unsafe_allow_html=True)` —
  e.g. a monospace or semi-condensed technical face for
  labels/metrics/data (reinforces "this is real telemetry") paired with
  a plain, high-legibility sans for body text. Do not leave Streamlit's
  default font.
- **Color:** define a real palette in `.streamlit/config.toml`, not the
  defaults — e.g. a near-black or deep slate background, one accent
  color used sparingly and consistently (not per-button rainbow), and
  status colors that follow ops conventions (green = up, amber = warn,
  red = critical) rather than decorative gradients.
- **Density and structure:** favor tables, sparklines, and compact
  metric rows over big card grids with large icons. Alerts should look
  like a log/incident feed, not a notification toast graveyard.
- **Icons/emoji:** use at most one small marker for status (●/▲/■ or a
  single consistent icon set), not an emoji per section header.
- **Motion:** none beyond Streamlit's built-in loading spinners — no
  fade-ins, no hover-lift cards.

**Practically for the coding assistant building this:**
- Set `[theme]` in `.streamlit/config.toml` explicitly (background,
  accent, text colors) rather than relying on defaults.
- Add one shared CSS block (in `app.py`, applied globally) defining
  typography, status colors, and spacing, instead of scattering ad hoc
  inline styles per page.
- When laying out the Dashboard, prefer `st.dataframe`/compact metric
  rows over large `st.columns` of icon+headline cards.
- Review the result against the "reject by default" list above before
  calling any page done.
