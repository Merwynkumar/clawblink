"""Telegram bot interface for ClawBlink. Users describe agents in plain English."""

import logging
import os
from pathlib import Path
import yaml

from providers import get_provider
from builder.config_builder import ConfigBuilder
from builder.config_validator import validate
from engine.runner import AgentRunner

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)


def run_telegram_bot() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN is required.\n"
            "Get one from @BotFather on Telegram, then add to .env:\n"
            "TELEGRAM_BOT_TOKEN=your-token-here"
        )

    from telegram import Update
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

    llm = get_provider()
    builder = ConfigBuilder(provider=llm)

    # Use a Telegram-specific configs directory so Telegram and WhatsApp
    # agents are stored and listed separately.
    root = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    telegram_configs = root / "configs" / "telegram"

    runner = AgentRunner(llm=llm, configs_dir=telegram_configs)
    runner.load_saved_configs()
    runner.start_scheduler()

    async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        await update.message.reply_text(
            "Welcome to ClawBlink!\n\n"
            "Describe an AI agent in plain English and I'll build it for you.\n\n"
            "Example messages:\n"
            '  "Monitor my GitHub repo user/repo for new issues and send me summaries"\n'
            '  "Every morning, check top Hacker News stories about AI and notify me"\n'
            '  "Watch example.com and alert me when the page changes"\n\n'
            "Commands:\n"
            "  /list  - Show all your running agents\n"
            "  /stop <name>  - Stop an agent\n"
            "  /run <name>  - Manually trigger an agent\n"
            "  /config <name>  - Show agent config\n"
            "  /status  - Show agent statuses"
        )

    async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        agents = runner.list_agents()
        if not agents:
            await update.message.reply_text("No agents running. Send me a message to create one!")
            return
        lines = []
        for a in agents:
            status = "running" if a["running"] else "stopped"
            sched = (
                f"daily at {a['time_local']}"
                if a.get("time_local")
                else (f"every {a['interval_minutes']}min" if a.get("interval_minutes") else "manual")
            )
            lines.append(f"  {a['name']} ({a['trigger_type']}, {sched}) - {status} - {a['run_count']} runs")
        await update.message.reply_text("Your agents:\n\n" + "\n".join(lines))

    async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        args = (update.message.text or "").split(maxsplit=1)
        if len(args) < 2:
            await update.message.reply_text("Usage: /stop <agent-name>")
            return
        name = args[1].strip()
        if runner.remove_agent(name):
            await update.message.reply_text(f"Agent '{name}' stopped and removed.")
        else:
            await update.message.reply_text(f"Agent '{name}' not found. Use /list to see running agents.")

    async def cmd_run(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        args = (update.message.text or "").split(maxsplit=1)
        if len(args) < 2:
            await update.message.reply_text("Usage: /run <agent-name>")
            return
        name = args[1].strip()
        if runner.get_config(name):
            await update.message.reply_text(
                f"Running '{name}'… You'll get the result in a moment."
            )
            runner.manual_trigger(name)
        else:
            await update.message.reply_text(f"Agent '{name}' not found. Use /list to see running agents.")

    async def cmd_config(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        args = (update.message.text or "").split(maxsplit=1)
        if len(args) < 2:
            await update.message.reply_text("Usage: /config <agent-name>")
            return
        name = args[1].strip()
        config = runner.get_config(name)
        if config:
            yaml_str = yaml.dump(config, default_flow_style=False, sort_keys=False)
            await update.message.reply_text(f"Config for '{name}':\n\n```\n{yaml_str}```", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"Agent '{name}' not found.")

    async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        agents = runner.list_agents()
        if not agents:
            await update.message.reply_text("No agents running.")
            return
        lines = [f"ClawBlink: {len(agents)} agent(s) running\n"]
        for a in agents:
            sch = (
                f" daily at {a['time_local']}"
                if a.get("time_local")
                else (f" every {a['interval_minutes']}min" if a.get("interval_minutes") else "")
            )
            lines.append(
                f"  {a['name']}\n"
                f"    Trigger: {a['trigger_type']}{sch}\n"
                f"    Runs: {a['run_count']}\n"
                f"    Status: {'active' if a['running'] else 'stopped'}"
            )
        await update.message.reply_text("\n".join(lines))

    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.message.text:
            return
        text = update.message.text.strip()
        if not text:
            return
        chat_id = str(update.message.chat_id)

        await update.message.reply_text(
            "Building your agent… (usually 30–60s; agent creation uses the LLM to turn your message into a config)"
        )

        try:
            config = builder.build(text, chat_id=chat_id)
        except ValueError as e:
            await update.message.reply_text(f"Could not create agent: {e}")
            return
        except Exception as e:
            logger.exception("Config build failed")
            err = str(e).lower()
            if "timeout" in err or "timed out" in err:
                await update.message.reply_text(
                    "Agent creation timed out (LLM took too long). Try again, or use a faster/smaller model "
                    "(e.g. Ollama: ollama run phi3) or set GEMINI_API_KEY in .env for cloud."
                )
            elif "api_key" in err or "apikey" in err or "401" in err or "403" in err:
                await update.message.reply_text(
                    "LLM API error. Check your API key in .env file.\n"
                    "Get a free Gemini key at: https://aistudio.google.com/apikey"
                )
            elif "11434" in err or "connection" in err:
                await update.message.reply_text(
                    "Could not reach Ollama. Make sure it's running:\n"
                    "  ollama serve\n\n"
                    "Or set GEMINI_API_KEY in .env for free cloud LLM."
                )
            else:
                await update.message.reply_text(f"Error: {e}")
            return

        errors = validate(config)
        if errors:
            error_msg = "\n".join(f"  - {e}" for e in errors)
            await update.message.reply_text(
                f"Generated config has issues:\n{error_msg}\n\n"
                "Try rephrasing your request more specifically."
            )
            return

        name = runner.add_agent(config)
        trigger = config.get("trigger", {})
        t_type = trigger.get("type", "manual")
        interval = trigger.get("interval_minutes", 0)
        time_local = trigger.get("time_local") or ""

        desc = config.get("description", "No description")
        if time_local:
            schedule_str = f"daily at {time_local}"
        elif interval:
            schedule_str = f"every {interval} minutes"
        else:
            schedule_str = f"manual (/run {name})"

        await update.message.reply_text(
            f"Agent created!\n\n"
            f"  Name: {name}\n"
            f"  Description: {desc}\n"
            f"  Schedule: {schedule_str}\n"
            f"  Actions: {len(config.get('actions', []))}\n\n"
            f"Commands:\n"
            f"  /run {name} - trigger now\n"
            f"  /config {name} - view config\n"
            f"  /stop {name} - stop agent\n"
            f"  /list - all agents"
        )

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("run", cmd_run))
    app.add_handler(CommandHandler("config", cmd_config))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("ClawBlink bot starting... Send /start in Telegram to begin.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
