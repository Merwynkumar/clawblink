# ClawBlink – No‑Code AI Agent Builder from Telegram / WhatsApp Chat

Describe an AI agent in **plain English** over Telegram or WhatsApp and get results back in the **same chat**.  
No code, no config files, no dashboards – just say what you want and ClawBlink builds and runs it.

```text
You: "Every morning at 8am, check BBC news and send me a digest."
You: "Every 10 minutes, explain me a Python concept with a simple example."
You: "Monitor my GitHub repo for new issues and summarize them."

ClawBlink: Agent created.
  Trigger: scheduled (daily 08:00) | actions: http_request → llm_analyze → notify
```

## ✨ Highlights

- **No‑code agents** – One chat message → working automation. News, prices, GitHub, reminders, tutorials.
- **Chat‑first** – Create, run, and control agents from **Telegram or WhatsApp**. No web UI.
- **Channel‑native** – Agents created in Telegram stay in Telegram; WhatsApp agents stay in WhatsApp (`configs/telegram` vs `configs/whatsapp`).
- **Local‑first** – Ollama, Gemini free tier, or any OpenAI‑compatible API. Your data, your machine.
- **Smart URLs** – At creation time, ClawBlink validates URLs and picks known-good sources (BBC, Python docs, prices, etc.) so agents get real data, not 404s.
- **Small & forkable** – Minimal Python codebase, easy to read and extend.

---

## 🧩 Features

| 📰 24/7 News Digest<br>BBC News Digest | 💼 AI Job Radar<br>LinkedIn AI Job Monitor | 🧠 Python Skill Tutor<br>Python Concept Agent | ⏰ Smart Routine Manager<br>Reminder Agents |
|---|---|---|---|
| <img src="docs/gifs/BBCNews.gif" width="220" /> | <img src="docs/gifs/LinkedinJobsMonitor.gif" width="220" /> | <img src="docs/gifs/Pythonprogramming.gif" width="220" /> | <img src="docs/gifs/Reminder.gif" width="220" /> |
| Discovery • Insights • Trends | Search • Filter • Alerts | Learn • Practice • Code | Schedule • Automate • Nudge |

---

## ⌨️ CLI quick commands

```bash
# Telegram
clawblink gateway

# WhatsApp Web (QR login)
clawblink channels login      # link device (scan QR)
clawblink channels gateway    # Node WhatsApp gateway
clawblink whatsapp-bridge     # Python bridge
```

---

## 📰 News

- **2025‑03‑10** – **ClawBlink launched.** No-code AI agents from Telegram and WhatsApp – describe what you want in plain English, get running automations in under a minute.
- **2025‑03‑09** – Smart agent creation: URLs validated at creation time, intent-based URLs (news, Python, prices, weather), and chat-readable outputs so every agent delivers useful results.

---

## 💡 Why ClawBlink?

ClawBlink is inspired by projects like [nanobot](https://github.com/HKUDS/nanobot), OpenClaw, and OneClaw – but focused on **one thing**: let anyone spin up useful background agents from chat, in minutes, without learning a new framework.

| | nanobot | OpenClaw / agent frameworks | OneClaw-style SaaS | ClawBlink |
|---|---|---|---|---|
| Create agents | Write Python skills | Design workflows / config | Click UI, pay monthly | Describe in plain English |
| Where it lives | CLI + many channels | Custom infra | Hosted dashboard | Your own Telegram bot and/or WhatsApp number |
| Setup | Install + configure | Multi-service setup | Account + payment | `pip install` + `.env` |
| Target user | Developers | Advanced devs | Anyone (SaaS) | Anyone who can chat |
| Codebase | ~4k+ LOC | Hundreds of k LOC | Closed source | ~1.9k LOC |
| Cost | Free | Free (but complex) | $/month | Free, self-hosted |

- If you want an **ultra-flexible research agent platform**, check out [nanobot](https://github.com/HKUDS/nanobot).
- If you want a **simple, forkable, no-code agent builder from chat**, ClawBlink is for you.

---

## 🎯 What ClawBlink Can Do

Send a message to your **Telegram bot** or **WhatsApp** – ClawBlink turns it into a real agent.

| Message | What you get |
|---|---|
| "Every morning, BBC news digest" | Scheduled agent, daily at 8am, fetch + summarize + notify. |
| "Every 10 minutes, explain a Python concept with an example" | Educational agent with one concept + code example per run. |
| "Watch my GitHub repo for new issues and summarize" | Polling agent → GitHub API → LLM summary → your chat. |
| "Bitcoin price every hour" | Price agent using a free API, results in chat. |
| "Remind me to drink water every 2 hours" | Simple reminder agent on a schedule. |

Agents are saved as YAML under `configs/telegram/` or `configs/whatsapp/`. You can edit them by hand or create everything from chat.

**Why does agent creation take 30–60 seconds?**  
ClawBlink uses an LLM to turn your message into a YAML config. You get "Building your agent…" immediately; "Agent created!" when the LLM finishes. Use a faster model (e.g. Gemini or a smaller Ollama model) for quicker creation.

---

## 📦 Install

```bash
git clone https://github.com/Merwynkumar/clawblink.git
cd clawblink

pip install -r requirements.txt
pip install -e .    # installs the `clawblink` CLI
cp .env.example .env
```

Edit `.env`:

- `TELEGRAM_BOT_TOKEN` from @BotFather
- One LLM: `OLLAMA_MODEL=...` or `GEMINI_API_KEY=...` or `OPENAI_API_KEY` + base URL + model

Update later: `git pull` then `pip install -e .`

---

## 🚀 Quick Start

<details>
<summary><strong>Telegram (recommended)</strong></summary>

```bash
clawblink gateway
```

1. Create a bot with @BotFather, put the token in `.env`.
2. In Telegram, open your bot → `/start`.
3. Send a plain-English request (e.g. "Every morning, BBC news digest").

**Commands:** `/list` · `/run <name>` · `/stop <name>` · `/config <name>` · `/status`

</details>

<details>
<summary><strong>WhatsApp (Web bridge)</strong></summary>

Requires **Node.js ≥18**.

1. **Link device:** `clawblink channels login` → scan QR in WhatsApp (Settings → Linked Devices).
2. **Run (two terminals):** `clawblink channels gateway` and `clawblink whatsapp-bridge`.
3. Chat from that WhatsApp number – same as Telegram: `/start`, then plain-English requests.

Agents created from WhatsApp are stored in `configs/whatsapp/` and only appear in WhatsApp `/list`.

</details>

---

## ⚙️ How It Works

```text
User message     "Every morning, BBC news digest"
       │
       ▼
ConfigBuilder    Plain English → YAML (with validated, intent-based URLs)
       │
       ▼
ConfigValidator  Structure + logic check
       │
       ▼
AgentRunner      Scheduler + triggers (scheduled / polling / manual)
       │
       ▼
Actions          http_request → llm_analyze → notify_telegram | notify_whatsapp
       │
       ▼
Result           Message in your chat
```

Data is always fetched by `http_request` first; the LLM only sees that text. No raw network access for the model.

---

## 🏗️ Architecture

```text
clawblink/
├── main.py                 # Telegram entry point
├── interfaces/
│   ├── cli.py              # clawblink gateway | channels login | whatsapp-bridge
│   ├── telegram_bot.py     # Telegram handlers
│   └── whatsapp_bridge.py  # WhatsApp HTTP bridge
├── builder/
│   ├── config_builder.py   # LLM: message → YAML (with URL validation & intent mapping)
│   └── config_validator.py
├── engine/
│   ├── runner.py           # Agent lifecycle + scheduler
│   ├── triggers/           # scheduled, polling, manual
│   └── actions/            # http_request, llm_analyze, notify_telegram, notify_whatsapp
├── providers/              # Ollama, Gemini, OpenAI-compatible
├── configs/
│   ├── telegram/           # Agents created from Telegram
│   └── whatsapp/           # Agents created from WhatsApp
├── bridge/whatsapp/        # Node.js WhatsApp Web (QR)
├── pyproject.toml
├── requirements.txt
└── .env.example
```

---

## ⏱️ Triggers

| Type | Description | Config |
|---|---|---|
| `scheduled` | Fixed interval or daily at a time | `interval_minutes` and/or `time_local: "08:00"` |
| `polling` | GitHub issues or URL change check | `source`, `repo` or `url`, `interval_minutes` |
| `manual` | Only when you run `/run <name>` | — |

---

## 🔧 Actions

| Type | Description |
|---|---|
| `http_request` | GET/POST URL, store in variable. Headers can use `env:VAR` for API keys. |
| `llm_analyze` | Run LLM on fetched data; output chat-readable text. |
| `notify_telegram` | Send message to Telegram (`chat_id` auto-filled when created from Telegram). |
| `notify_whatsapp` | Send message via WhatsApp Web bridge (`to` set when created from WhatsApp). |

Pattern: `http_request` → optional `llm_analyze` → `notify_telegram` or `notify_whatsapp`.

---

## 📋 Dependencies

- **requests** – HTTP client
- **python-telegram-bot** – Telegram bot API
- **pyyaml** – YAML config parsing
- **flask** – WhatsApp Web bridge server

---

## 🤝 Contributing

- **New triggers** – RSS, webhooks, email, or other event sources.
- **New actions** – Slack/Discord notifications, email, file writes, etc.
- **Smarter builder** – More intent→URL mappings, better validation heuristics.
- **Example agents & docs** – Great starter agents or walkthroughs.

If you build something with ClawBlink, share it in an issue or PR.

---

## 📄 License

MIT
