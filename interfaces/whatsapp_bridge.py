"""WhatsApp Web bridge interface for ClawBlink.

This module exposes a small HTTP server that the Node-based WhatsApp
bridge (bridge/whatsapp/gateway.js) can call.

Flow:
  - Node gateway receives messages from WhatsApp Web and POSTs them to
    /whatsapp/incoming on this server.
  - This module reuses ConfigBuilder + AgentRunner to handle commands
    and agent creation, just like the Telegram bot.
  - To send replies back to WhatsApp, this server POSTs to the Node
    gateway at http://127.0.0.1:8071/send.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

import requests
from flask import Flask, jsonify, request

from providers import get_provider
from builder.config_builder import ConfigBuilder
from builder.config_validator import validate
from engine.runner import AgentRunner

logger = logging.getLogger(__name__)


def _load_dotenv() -> None:
    """Lightweight .env loader (same behavior as main.py)."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(root, ".env")
    if not os.path.isfile(env_path):
        return
    try:
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    key, value = key.strip(), value.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = value
    except OSError:
        pass


def create_app() -> Flask:
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )

    llm = get_provider()
    builder = ConfigBuilder(provider=llm)
    runner = AgentRunner(llm=llm)
    runner.load_saved_configs()
    runner.start_scheduler()

    node_send_url = os.environ.get(
        "CLAWBLINK_WHATSAPP_SEND_URL", "http://127.0.0.1:8071/send"
    )

    app = Flask(__name__)

    def _send_whatsapp(to: str, text: str) -> None:
        payload: Dict[str, Any] = {"to": to, "text": text}
        try:
            resp = requests.post(node_send_url, json=payload, timeout=10)
            if not resp.ok:
                logger.warning("WhatsApp send failed via bridge: %s", resp.text[:200])
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("WhatsApp send error via bridge: %s", e)

    @app.get("/health")
    def health() -> Any:
        return jsonify({"status": "ok"})

    @app.post("/whatsapp/incoming")
    def whatsapp_incoming() -> Any:
        try:
            data = request.get_json(force=True) or {}
        except Exception:
            data = {}

        from_number = str(data.get("from", "")).strip()
        body = str(data.get("body", "")).strip()

        if not from_number or not body:
            return jsonify({"ok": True})

        text = body

        # Commands
        if text.lower().startswith("/start"):
            _send_whatsapp(
                from_number,
                (
                    "Welcome to ClawBlink (WhatsApp)!\n\n"
                    "Describe an AI agent in plain English and I'll build it for you.\n\n"
                    "Example messages:\n"
                    '  "Monitor my GitHub repo user/repo for new issues and send me summaries"\n'
                    '  "Every morning, check top Hacker News stories about AI and notify me"\n'
                    '  "Watch example.com and alert me when the page changes"\n\n'
                    "Commands:\n"
                    "  /list  - Show all running agents\n"
                    "  /stop <name>  - Stop an agent\n"
                    "  /run <name>  - Manually trigger an agent\n"
                    "  /config <name>  - Show agent config\n"
                    "  /status  - Show agent statuses"
                ),
            )
            return jsonify({"ok": True})

        if text.lower().startswith("/list"):
            agents = runner.list_agents()
            if not agents:
                _send_whatsapp(from_number, "No agents running. Send me a message to create one!")
                return jsonify({"ok": True})
            lines = ["Your agents:\n"]
            for a in agents:
                status = "running" if a["running"] else "stopped"
                interval = (
                    f"every {a['interval_minutes']}min"
                    if a["interval_minutes"]
                    else "manual"
                )
                lines.append(
                    f"- {a['name']} ({a['trigger_type']}, {interval}) "
                    f"- {status} - {a['run_count']} runs"
                )
            _send_whatsapp(from_number, "\n".join(lines))
            return jsonify({"ok": True})

        if text.lower().startswith("/stop"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                _send_whatsapp(from_number, "Usage: /stop <agent-name>")
                return jsonify({"ok": True})
            name = parts[1].strip()
            if runner.remove_agent(name):
                _send_whatsapp(from_number, f"Agent '{name}' stopped and removed.")
            else:
                _send_whatsapp(
                    from_number,
                    f"Agent '{name}' not found. Use /list to see running agents.",
                )
            return jsonify({"ok": True})

        if text.lower().startswith("/run "):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                _send_whatsapp(from_number, "Usage: /run <agent-name>")
                return jsonify({"ok": True})
            name = parts[1].strip()
            if runner.manual_trigger(name):
                _send_whatsapp(
                    from_number, f"Agent '{name}' triggered manually. Results coming soon..."
                )
            else:
                _send_whatsapp(
                    from_number,
                    f"Agent '{name}' not found. Use /list to see running agents.",
                )
            return jsonify({"ok": True})

        if text.lower().startswith("/config "):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                _send_whatsapp(from_number, "Usage: /config <agent-name>")
                return jsonify({"ok": True})
            name = parts[1].strip()
            config = runner.get_config(name)
            if config:
                try:
                    yaml_str = json.dumps(config, indent=2)
                except TypeError:
                    yaml_str = str(config)
                _send_whatsapp(from_number, f"Config for '{name}':\n\n{yaml_str}")
            else:
                _send_whatsapp(from_number, f"Agent '{name}' not found.")
            return jsonify({"ok": True})

        if text.lower().startswith("/status"):
            agents = runner.list_agents()
            if not agents:
                _send_whatsapp(from_number, "No agents running.")
                return jsonify({"ok": True})
            lines = [f"ClawBlink: {len(agents)} agent(s) running\n"]
            for a in agents:
                lines.append(
                    f"- {a['name']}\n"
                    f"  Trigger: {a['trigger_type']}"
                    + (
                        f" (every {a['interval_minutes']}min)"
                        if a["interval_minutes"]
                        else ""
                    )
                    + f"\n  Runs: {a['run_count']}"
                    + f"\n  Status: {'active' if a['running'] else 'stopped'}"
                )
            _send_whatsapp(from_number, "\n".join(lines))
            return jsonify({"ok": True})

        # Otherwise: treat as a request to create a new agent.
        _send_whatsapp(from_number, "Building your agent...")

        try:
            config = builder.build(text, chat_id=None)
        except ValueError as e:
            _send_whatsapp(from_number, f"Could not create agent: {e}")
            return jsonify({"ok": True})
        except Exception as e:  # pragma: no cover - defensive
            logger.exception("WhatsApp config build failed")
            err = str(e).lower()
            if "api_key" in err or "apikey" in err or "401" in err or "403" in err:
                _send_whatsapp(
                    from_number,
                    "LLM API error. Check your API key in .env file.\n"
                    "You can use Ollama locally or set GEMINI_API_KEY / OPENAI_API_KEY.",
                )
            elif "11434" in err or "connection" in err:
                _send_whatsapp(
                    from_number,
                    "Could not reach Ollama. Make sure it's running:\n"
                    "  ollama serve\n\n"
                    "Or set GEMINI_API_KEY / OPENAI_API_KEY in .env for a cloud LLM.",
                )
            else:
                _send_whatsapp(from_number, f"Error: {e}")
            return jsonify({"ok": True})

        # Rewrite notify_telegram actions to notify_whatsapp for this number.
        actions = config.get("actions") or []
        for action in actions:
            if isinstance(action, dict) and action.get("type") == "notify_telegram":
                action["type"] = "notify_whatsapp"
                action.pop("chat_id", None)
                action.setdefault("to", from_number)

        errors = validate(config)
        if errors:
            error_msg = "\n".join(f"- {e}" for e in errors)
            _send_whatsapp(
                from_number,
                "Generated config has issues:\n"
                f"{error_msg}\n\n"
                "Try rephrasing your request more specifically.",
            )
            return jsonify({"ok": True})

        name = runner.add_agent(config)
        trigger = config.get("trigger", {})
        t_type = trigger.get("type", "manual")
        interval = trigger.get("interval_minutes", 0)

        desc = config.get("description", "No description")
        schedule_str = (
            f"every {interval} minutes" if interval else f"manual (/run {name})"
        )

        _send_whatsapp(
            from_number,
            "Agent created!\n\n"
            f"  Name: {name}\n"
            f"  Description: {desc}\n"
            f"  Trigger: {t_type} ({schedule_str})\n"
            f"  Actions: {len(actions)}\n\n"
            "Commands:\n"
            f"  /run {name} - trigger now\n"
            f"  /config {name} - view config\n"
            f"  /stop {name} - stop agent\n"
            "  /list - all agents",
        )

        return jsonify({"ok": True})

    return app


def run_whatsapp_bridge() -> None:
    _load_dotenv()
    port = int(os.environ.get("WHATSAPP_BRIDGE_PORT", "8070"))
    app = create_app()
    logger.info("Starting ClawBlink WhatsApp bridge on port %d", port)
    app.run(host="127.0.0.1", port=port)


if __name__ == "__main__":
    run_whatsapp_bridge()

