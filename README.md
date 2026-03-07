# ClawBlink

**ClawBlink AI CLI** — a minimal command-line interface project.

## Setup

```bash
pip install -r requirements.txt
```

## Usage

Run the CLI as a module:

```bash
python -m clawblink.cli hello
python -m clawblink.cli hello --name "Your Name"
python -m clawblink.cli version
```

Or install in development mode and use the `clawblink` command (after adding an entry point in `pyproject.toml` or installing with `pip install -e .`).

## Project structure

```
clawblink/
├── clawblink/
│   ├── __init__.py
│   └── cli.py
├── README.md
├── requirements.txt
└── .gitignore
```
