# ClawBlink – No‑Code AI Agent Builder from Telegram / WhatsApp Chat

Describe an AI agent in plain English over **Telegram or WhatsApp** and get results back on the **same chat app**.  
ClawBlink turns your messages into real, running automations – no code, no config files, no dashboards.

```text
Telegram:
  You: "Monitor my GitHub repo for new issues and send me AI summaries."

WhatsApp:
  You: "Every morning at 8am, check top AI news and send me a digest here."

ClawBlink (both):
  Agent created.
    name: github-issue-monitor
    trigger: every 5 minutes
    actions: http_request → llm_analyze → notify_(telegram|whatsapp)
```

## Highlights

- **No‑code agents**: Build background agents from a single chat message.
- **Chat‑first**: Configure and control agents from **Telegram or WhatsApp** – no web UI.
- **Channel‑native**: Agents created from Telegram reply on Telegram; agents created from WhatsApp reply on WhatsApp.
- **Local‑first friendly**: Works with Ollama, Gemini free tier, or any OpenAI‑compatible endpoint via a SmartProvider.
- **Tiny codebase**: Roughly 700–900 lines of Python, easy to fork and hack.

---

## News

- **2026‑03‑07** – Gold price agent now uses real COMEX futures data (Yahoo Finance GC=F) with smart HTTP error handling.
- **2026‑03‑06** – Added SmartProvider (Ollama + Gemini + OpenAI‑compatible fallbacks) and stricter YAML validation.
- **2026‑03‑05** – Pivoted ClawBlink into a no‑code agent builder that runs entirely from Telegram chat.

---

## Why ClawBlink?

ClawBlink is inspired by projects like [nanobot](https://github.com/HKUDS/nanobot), OpenClaw, and OneClaw – but focused on **one thing only**: letting anyone spin up useful background agents from chat, in minutes, without learning a new framework.

| | nanobot | OpenClaw / agent frameworks | OneClaw‑style SaaS | **ClawBlink** |
|---|---|---|---|---|
| Create agents | Write Python skills | Design workflows / config | Click UI, pay monthly | **Describe in plain English** |
| Where it lives | CLI + many channels | Custom infra | Hosted dashboard | **Your own Telegram bot and/or WhatsApp number** |
| Setup | Install + configure | Multi‑service setup | Account + payment | **`pip install` + `.env`** |
| Target user | Developers | Advanced devs | Anyone (SaaS) | **Anyone who can chat** |
| Codebase | ~4k+ LOC | Hundreds of k LOC | Closed source | **~750 LOC** |
| Cost | Free | Free (but complex) | $ / month | **Free, self‑hosted** |

If you want an ultra‑flexible research agent platform, check out [nanobot](https://github.com/HKUDS/nanobot).  
If you want a **simple, forkable, no‑code agent builder from chat**, ClawBlink is for you.

---

## What ClawBlink Can Do

Just send a message to your **Telegram bot** or **WhatsApp number**. ClawBlink takes care of LLM prompts, YAML config, triggers, actions, and scheduling.  
Whatever channel you start from is where you’ll see the results.

| Message | What ClawBlink builds |
|---|---|
| "Watch my GitHub repo `user/repo` for new issues and summarize them" | Polling agent that hits the GitHub Issues API every N minutes, runs `llm_analyze`, and sends you a summary in the same chat (Telegram or WhatsApp). |
| "Every morning check top AI news and send me a digest" | Scheduled agent that fetches a news source, strips HTML, summarizes with LLM, and notifies you in your chat app. |
| "Monitor example.com and alert me when the page changes" | URL‑polling agent comparing page snapshots and sending change alerts. |
| "Check Bitcoin price every hour and alert if it drops 5%" | Price‑check agent using a public API, with an LLM explaining changes in plain English. |
| "Give me gold price in USD and INR every 5 minutes" | Gold‑price agent using Yahoo Finance GC=F, with per‑gram and INR conversion. |

You can also create agents manually by dropping YAML files into `configs/`, but you never have to.

---

## Quick Start (Telegram only)

```bash
# 1. Clone
git clone https://github.com/Merwynkumar/clawblink.git
cd clawblink

# 2. Install deps (recommended: a virtualenv)
pip install -r requirements.txt

# 3. Configure (add your keys to .env)
cp .env.example .env
# Edit .env: set TELEGRAM_BOT_TOKEN and either GEMINI_API_KEY or an OPENAI-compatible endpoint / OLLAMA_MODEL

# 4. Run the Telegram bot
python main.py
```

Then open your Telegram bot and start describing agents.

---

## Telegram Commands

| Command | Description |
|---|---|
| `/start` | Show welcome message and basic help. |
| `/list` | List all running agents (name, trigger, run count). |
| `/run <name>` | Manually trigger an agent immediately. |
| `/stop <name>` | Stop an agent and remove its YAML config. |
| `/config <name>` | View the YAML config that defines an agent. |
| `/status` | Detailed status of all agents (last run, intervals, etc.). |

Any plain chat message that is **not** a command is treated as a request to create a new agent.

---

## WhatsApp Bot & Notifications (WhatsApp only)

ClawBlink also supports a **full WhatsApp chat interface** (same behavior as Telegram) plus WhatsApp notifications.

You can choose:

- **Telegram only** – run `python main.py`
- **WhatsApp only** – run `python -m interfaces.whatsapp_twilio`
- **Both** – run both processes in parallel and use whichever app you prefer

### 1. Enable WhatsApp in Twilio

1. Create or sign in to your Twilio account.
2. Enable the **WhatsApp Sandbox** or configure a WhatsApp Business sender.
3. Copy:
   - `Account SID`
   - `Auth Token`
   - WhatsApp **From** number (looks like `whatsapp:+14155238886`).

### 2. Set environment variables

In your `.env`:

```bash
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your-auth-token
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
```

### 3. Run the WhatsApp bot

In a separate terminal from the Telegram bot (or as your only process if you only want WhatsApp):

```bash
python -m interfaces.whatsapp_twilio
```

The bot listens on `http://0.0.0.0:8000/whatsapp` by default; change the port with `WHATSAPP_PORT` in `.env`.

### 4. Use `notify_whatsapp` in an agent

Add a `notify_whatsapp` action to any agent config:

```yaml
actions:
  - type: http_request
    method: GET
    url: https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd
    output: btc_raw

  - type: llm_analyze
    prompt: |
      Here is Bitcoin price data:
      {btc_raw}
      Explain the current price in simple terms.
    output: analysis

  - type: notify_whatsapp
    to: "whatsapp:+911234567890"
    message: "{analysis}"
```

Agents created from WhatsApp will typically end with `notify_whatsapp` so results stay in WhatsApp.  
If you want multi‑channel behavior, you can mix `notify_telegram` and `notify_whatsapp` actions in the same YAML config.

---

## How It Works (End‑to‑End)

```text
User message        "Monitor GitHub issues and notify me"
     │
     ▼
ConfigBuilder       LLM converts plain English → YAML agent config
     │
     ▼
ConfigValidator     Validates structure (trigger + actions + fields)
     │
     ▼
AgentRunner         Loads/saves config, starts background scheduler
     │
     ▼
Trigger fires       scheduled / polling / manual
     │
     ▼
Actions pipeline    http_request → llm_analyze → notify_(telegram|whatsapp)
     │
     ▼
Result              Summarized result arrives in your chat app
```

LLMs only ever see **text data** fetched by `http_request` – they never get raw network access. This keeps behavior predictable and easier to debug.

---

## Architecture Overview

```text
clawblink/                    ~750 lines of Python
├── main.py                   # Entry point – starts Telegram bot
├── providers/                # LLM providers + SmartProvider
│   ├── __init__.py           # SmartProvider (OpenAI‑compat, Gemini, Ollama)
│   ├── openai_compat_provider.py
│   ├── gemini_provider.py
│   └── ollama_provider.py
├── builder/
│   ├── __init__.py
│   ├── config_builder.py     # LLM: user message → YAML config
│   └── config_validator.py   # Structural + logical validation
├── engine/
│   ├── __init__.py
│   ├── runner.py             # Agent lifecycle + scheduler loop
│   ├── triggers/
│   │   ├── scheduled.py      # Run on interval (every N minutes)
│   │   ├── polling.py        # GitHub issues, generic URLs, etc.
│   │   └── manual.py         # /run command
│   └── actions/
│       ├── llm_analyze.py    # LLM analysis on fetched data
│       ├── notify_telegram.py# Send Telegram message
│       ├── notify_whatsapp.py# Send WhatsApp message via Twilio
│       └── http_request.py   # GET/POST any API, HTML → text
├── interfaces/
│   ├── __init__.py
│   ├── telegram_bot.py       # Telegram bot handlers + wiring
│   └── whatsapp_twilio.py    # WhatsApp webhook (Twilio) + handlers
├── configs/                  # Saved agent YAML configs
├── pyproject.toml            # Project metadata
├── requirements.txt          # Minimal dependencies
└── .env.example              # Environment config template
```

---

## Setup

<details>
<summary><strong>Telegram setup</strong> (chat + notifications)</summary>

### 1. Get a Telegram Bot Token

1. Open Telegram, search for `@BotFather`.
2. Send `/newbot`, follow the prompts.
3. Copy the bot token into your `.env` as `TELEGRAM_BOT_TOKEN`.

### 2. Choose an LLM Provider

ClawBlink uses a **SmartProvider** that can choose from:

- **Ollama** (local, free, no API key) – great default.
- **Gemini** free tier.
- Any **OpenAI‑compatible** endpoint (OpenAI, DeepSeek, Groq, Together, OpenRouter, etc.).

See `.env.example` for all supported options. Typical options:

```bash
# Local Ollama (recommended if you have a GPU/CPU that can run models)
OLLAMA_MODEL=qwen2.5-coder:7b

# Or: Gemini free tier
GEMINI_API_KEY=your-gemini-key-here

# Or: any OpenAI‑compatible endpoint
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1   # or another provider
OPENAI_MODEL=gpt-4.1-mini
```

### 3. Configure `.env`

```bash
cp .env.example .env
```

Then edit `.env` and set at least:

- `TELEGRAM_BOT_TOKEN=...`
- One of: `OLLAMA_MODEL`, `GEMINI_API_KEY`, or (`OPENAI_API_KEY` + `OPENAI_BASE_URL` + `OPENAI_MODEL`).

### 4. Run ClawBlink (Telegram)

```bash
pip install -r requirements.txt
python main.py
```

Leave `python main.py` running – it powers your Telegram bot and scheduler.

</details>

<details>
<summary><strong>WhatsApp setup</strong> (chat + notifications via Twilio)</summary>

### 1. Enable WhatsApp in Twilio

1. Create or sign in to your Twilio account.
2. Enable the **WhatsApp Sandbox** or configure a WhatsApp Business sender.
3. Copy from the Twilio console:
   - `Account SID`
   - `Auth Token`
   - WhatsApp **From** number (looks like `whatsapp:+14155238886`).

### 2. Configure `.env` for WhatsApp

In your `.env`:

```bash
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your-auth-token
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
```

You can run WhatsApp **with or without** Telegram. If you want WhatsApp‑only, you do not need `TELEGRAM_BOT_TOKEN`.

### 3. Run the WhatsApp bot

In a terminal:

```bash
pip install -r requirements.txt
python -m interfaces.whatsapp_twilio
```

The bot listens on `http://0.0.0.0:8000/whatsapp` by default; change the port with `WHATSAPP_PORT` in `.env`.  
Point your Twilio WhatsApp webhook URL at `https://<your-public-url>/whatsapp` (for example via ngrok).

Once running, you can message your Twilio WhatsApp number with `/start`, `/list`, or a plain‑English request to create agents.

</details>

---

## Agent Config Format (YAML)

ClawBlink generates YAML configs automatically, but they are plain files in `configs/` and you can edit or add them manually.

```yaml
name: github-issue-monitor
description: Monitors GitHub for new issues and sends AI summaries

trigger:
  type: polling
  source: github_issues
  repo: "octocat/Hello-World"
  interval_minutes: 5

actions:
  - type: http_request
    method: GET
    url: https://api.github.com/repos/octocat/Hello-World/issues
    output: issues_raw

  - type: llm_analyze
    prompt: |
      Summarize these GitHub issues and rate priority (low/medium/high).
      Data:
      {issues_raw}
    output: summary

  - type: notify_telegram
    message: "New issues in {repo}:\n{summary}"

llm:
  provider: smart
```

You can inspect any agent’s config with `/config <name>` in Telegram.

---

## Triggers

| Type | Description | Config fields |
|---|---|---|
| `scheduled` | Runs on a fixed interval. | `interval_minutes` |
| `polling` | Polls an external source (GitHub, URL, etc.) for changes. | `source` (`github_issues`, `url_check`, `generic`), `repo` or `url`, `interval_minutes` |
| `manual` | Only fires when you call `/run <name>`. | (none) |

---

## Actions

| Type | Description | Key fields |
|---|---|---|
| `http_request` | Fetch data from any HTTP API or URL. | `url`, `method`, `headers`, `output` |
| `llm_analyze` | Run an LLM on previously fetched data. | `prompt` (with `{variables}`), `output` |
| `notify_telegram` | Send a formatted message to Telegram. | `message` (with `{variables}`), `chat_id` (optional, auto‑filled) |
| `notify_whatsapp` | Send a formatted message to WhatsApp via Twilio. | `message` (with `{variables}`), `to` (e.g. `whatsapp:+911234567890`) |

The usual pattern is:

```text
http_request → llm_analyze → notify_(telegram|whatsapp)
```

The builder and validator enforce that **if an agent needs internet data**, it must first use `http_request` before `llm_analyze`.

---

## Dependencies

ClawBlink intentionally keeps its dependency list short:

```text
requests              # HTTP client
python-telegram-bot   # Telegram interface
pyyaml                # YAML parsing
flask                 # WhatsApp webhook server (Twilio)
```

---

## Contributing

ClawBlink is intentionally small and hackable. PRs are welcome, especially for:

- New trigger types (RSS feeds, email inbox polling, Discord webhooks).
- New action types (Slack notify, Discord notify, file write, email).
- New providers or smarter SmartProvider heuristics.
- Better example agents and docs.

If you build something cool with ClawBlink, consider opening an issue or PR and linking your agents so others can try them.

---

## License

MIT
