"""ClawBlink -- No-Code AI Agent Builder from Chat.

Describe an AI agent in plain English. ClawBlink builds and runs it.
No code, no config, no setup.
"""

import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _load_dotenv() -> None:
    """Load .env from project root into os.environ (only if not already set)."""
    env_path = os.path.join(_ROOT, ".env")
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


from interfaces.telegram_bot import run_telegram_bot


def main() -> None:
    _load_dotenv()
    run_telegram_bot()


if __name__ == "__main__":
    main()
