"""ClawBlink CLI – simple gateway-style commands.

This provides a `clawblink` command that mirrors the feel of `nanobot`:

Examples:

  clawblink gateway
      Run the main ClawBlink gateway (Telegram bot).

  clawblink channels login
      Run the WhatsApp Web login flow (QR code in terminal).

  clawblink channels gateway
      Run the WhatsApp Web Node gateway (bridge to/from WhatsApp).

  clawblink whatsapp-bridge
      Run the Python WhatsApp bridge HTTP server (talks to Node gateway).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WHATSAPP_NODE_DIR = ROOT / "bridge" / "whatsapp"


def _run_telegram_gateway() -> None:
    # Ensure project root is on sys.path so `main` is importable
    root_str = str(ROOT)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

    from main import main as telegram_main

    telegram_main()


def _run_whatsapp_bridge() -> None:
    from interfaces.whatsapp_bridge import run_whatsapp_bridge

    run_whatsapp_bridge()


def _run_npm_script(script: str) -> None:
    if not WHATSAPP_NODE_DIR.exists():
        print("WhatsApp bridge directory not found:", WHATSAPP_NODE_DIR, file=sys.stderr)
        sys.exit(1)

    # Use shell=True so we behave exactly like the user typing
    # `npm run <script>` in their own terminal, which respects PATH.
    cmd = f"npm run {script}"
    try:
        # Inherit stdin/stdout/stderr so the user can see QR codes and logs.
        subprocess.run(cmd, cwd=str(WHATSAPP_NODE_DIR), shell=True, check=True)
    except subprocess.CalledProcessError as e:
        # Propagate non-zero exit code but keep message simple.
        sys.exit(e.returncode)


def _run_channels_login() -> None:
    """Run the WhatsApp Web login flow (QR code)."""
    _run_npm_script("login")


def _run_channels_gateway() -> None:
    """Run the WhatsApp Web Node gateway."""
    _run_npm_script("gateway")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="clawblink", description="ClawBlink – no-code agents from chat.")
    subparsers = parser.add_subparsers(dest="command")

    # Main gateway (Telegram) – matches `nanobot gateway` style.
    p_gateway = subparsers.add_parser(
        "gateway",
        help="Run the main ClawBlink gateway (Telegram bot).",
    )
    p_gateway.set_defaults(func=lambda _args: _run_telegram_gateway())

    # WhatsApp Web: Python bridge HTTP server.
    p_wabr = subparsers.add_parser(
        "whatsapp-bridge",
        help="Run the Python WhatsApp bridge HTTP server (talks to Node gateway).",
    )
    p_wabr.set_defaults(func=lambda _args: _run_whatsapp_bridge())

    # Channels namespace – mirrors `nanobot channels <subcommand>`.
    p_channels = subparsers.add_parser(
        "channels",
        help="Channel-related helpers (e.g. WhatsApp Web login & gateway).",
    )
    channels_sub = p_channels.add_subparsers(dest="channels_command")

    p_channels_login = channels_sub.add_parser(
        "login",
        help="Run the WhatsApp Web QR-code login flow.",
    )
    p_channels_login.set_defaults(func=lambda _args: _run_channels_login())

    p_channels_gateway = channels_sub.add_parser(
        "gateway",
        help="Run the WhatsApp Web Node gateway.",
    )
    p_channels_gateway.set_defaults(func=lambda _args: _run_channels_gateway())

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    # No subcommand: show help.
    if not getattr(args, "command", None):
        parser.print_help()
        sys.exit(1)

    # For `channels`, ensure a subcommand is chosen.
    if args.command == "channels" and not getattr(args, "channels_command", None):
        parser.parse_args(["channels", "--help"])
        sys.exit(1)

    func = getattr(args, "func", None)
    if not func:
        parser.print_help()
        sys.exit(1)

    func(args)


if __name__ == "__main__":
    main()

