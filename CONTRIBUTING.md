# Contributing

This is a v0.1 reference implementation. Changes that keep the schema evolvable (extra fields ignored) are preferred over breaking field renames.

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest
```

## Rules

- Never add code that generates, stores, logs, or transmits private keys, seeds, or PEM files.
- Do not claim this project is an official Technocore component.
- New capabilities go in `src/tar/taxonomy.py` — do not invent a protocol version bump for a new cap id.
- Swarm messaging, task delegation, and reputation scores are labeled FUTURE. Do not ship a half-network.
- Tests must stay green. Add coverage for new routes.
- Fictional demo agents must stay clearly labeled FICTIONAL.

## Pull requests

1. Open an issue first for taxonomy or protocol changes (see `.github/ISSUE_TEMPLATE`).
2. Include tests.
3. Run `ruff check src tests` if ruff is installed.
