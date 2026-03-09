"""WhatsApp chat interface for ClawBlink using Twilio webhooks.

This provides a WhatsApp experience parallel to the Telegram bot:
users can send plain-English requests or slash commands, and
ClawBlink will build and run agents for them.

Usage (development):
  1) Configure Twilio WhatsApp sandbox and set webhook URL to
     https://<your-public-url>/whatsapp
     (via ngrok, Cloudflared tunnel, etc.)
  2) Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM
     in .env (see .env.example).
  3) Run:
       python -m interfaces.whatsapp_twilio
"""

import logging
import os
from typing import Any, Dict

from flask import Flask, Request, Response, request

from providers import get_provider
from builder.config_builder import ConfigBuilder
from builder.config_validator import validate
from engine.runner import AgentRunner
from engine.actions import notify_whatsapp

logger = logging.getLogger(__name__)


def _load_dotenv() -> None:
    """Small .env loader (duplicated from main.py to avoid circular import)."""
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


def _send_whatsapp(to_number: str, text: str) -> None:
    """Send a WhatsApp message using the same logic as notify_whatsapp action."""
    action: Dict[str, Any] = {"type": "notify_whatsapp", "to": to_number, "message": text}
    notify_whatsapp.execute(action, variables={})


def create_app() -> Flask:
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
    )

    llm = get_provider()
    builder = ConfigBuilder(provider=llm)
    runner = AgentRunner(llm=llm)
    runner.load_saved_configs()
    runner.start_scheduler()

    app = Flask(__name__)

    @app.post("/whatsapp")
    def whatsapp_webhook() -> Response:
        req: Request = request
        from_number = (req.form.get("From") or "").strip()
        body = (req.form.get("Body") or "").strip()

        if not from_number or not body:
            return Response("", status=200)

        text = body

        # Commands
        if text.lower().startswith("/start"):
            _send_whatsapp(
                from_number,
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
                "  /status  - Show agent statuses",
            )
            return Response("", status=200)

        if text.lower().startswith("/list"):
            agents = runner.list_agents()
            if not agents:
                _send_whatsapp(from_number, "No agents running. Send me a message to create one!")
                return Response("", status=200)
            lines = ["Your agents:\n"]
            for a in agents:
                status = "running" if a["running"] else "stopped"
                interval = f"every {a['interval_minutes']}min" if a["interval_minutes"] else "manual"
                lines.append(f"- {a['name']} ({a['trigger_type']}, {interval}) - {status} - {a['run_count']} runs")
            _send_whatsapp(from_number, "\n".join(lines))
            return Response("", status=200)

        if text.lower().startswith("/stop"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                _send_whatsapp(from_number, "Usage: /stop <agent-name>")
                return Response("", status=200)
            name = parts[1].strip()
            if runner.remove_agent(name):
                _send_whatsapp(from_number, f"Agent '{name}' stopped and removed.")
            else:
                _send_whatsapp(from_number, f"Agent '{name}' not found. Use /list to see running agents.")
            return Response("", status=200)

        if text.lower().startswith("/run "):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                _send_whatsapp(from_number, "Usage: /run <agent-name>")
                return Response("", status=200)
            name = parts[1].strip()
            if runner.manual_trigger(name):
                _send_whatsapp(from_number, f"Agent '{name}' triggered manually. Results coming soon...")
            else:
                _send_whatsapp(from_number, f"Agent '{name}' not found. Use /list to see running agents.")
            return Response("", status=200)

        if text.lower().startswith("/config "):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                _send_whatsapp(from_number, "Usage: /config <agent-name>")
                return Response("", status=200)
            name = parts[1].strip()
            config = runner.get_config(name)
            if config:
                import yaml

                yaml_str = yaml.dump(config, default_flow_style=False, sort_keys=False)
                _send_whatsapp(from_number, f"Config for '{name}':\n\n{yaml_str}")
            else:
                _send_whatsapp(from_number, f"Agent '{name}' not found.")
            return Response("", status=200)

        if text.lower().startswith("/status"):
            agents = runner.list_agents()
            if not agents:
                _send_whatsapp(from_number, "No agents running.")
                return Response("", status=200)
            lines = [f"ClawBlink: {len(agents)} agent(s) running\n"]
            for a in agents:
                lines.append(
                    f"- {a['name']}\n"
                    f"  Trigger: {a['trigger_type']}"
                    + (f" (every {a['interval_minutes']}min)" if a["interval_minutes"] else "")
                    + f"\n  Runs: {a['run_count']}"
                    + f"\n  Status: {'active' if a['running'] else 'stopped'}"
                )
            _send_whatsapp(from_number, "\n".join(lines))
            return Response("", status=200)

        # Otherwise: treat as a request to create a new agent
        _send_whatsapp(from_number, "Building your agent...")

        try:
            # Build config from natural language. We don't pass chat_id because
            # this is a WhatsApp channel; we map notifications below.
            config = builder.build(text, chat_id=None)
        except ValueError as e:
            _send_whatsapp(from_number, f"Could not create agent: {e}")
            return Response("", status=200)
        except Exception as e:  # pragma: no cover - defensive logging
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
            return Response("", status=200)

        # Convert any notify_telegram actions into notify_whatsapp actions for this number
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
            return Response("", status=200)

        name = runner.add_agent(config)
        trigger = config.get("trigger", {})
        t_type = trigger.get("type", "manual")
        interval = trigger.get("interval_minutes", 0)

        desc = config.get("description", "No description")
        schedule_str = f"every {interval} minutes" if interval else f"manual (/run {name})"

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

        return Response("", status=200)

    return app


def main() -> None:
    _load_dotenv()
    port = int(os.environ.get("WHATSAPP_PORT", "8000"))
    app = create_app()
    logger.info("Starting ClawBlink WhatsApp webhook on port %d", port)
    # Host 0.0.0.0 so it works behind tunnels like ngrok
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()

