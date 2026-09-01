# Contributing

This is a v1.0.0 reference implementation. Changes that keep the schema evolvable (extra fields ignored) are preferred over breaking field renames.

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest
```

## Rules

- Never add code that generates, stores, logs, or transmits private keys, seeds, or PEM files except into gitignored local demo key files that are never printed.
- Do not claim this project is an official Technocore component.
- New capabilities go in `src/tar/data/taxonomy.json` — do not invent a protocol version bump for a new cap id.
- Do not auto-verify capability claims. Honor TASK → ACCEPT → SUBMIT → VOUCH.
- No tokenomics, monetary rewards, or fake reputation scores.
- Demo agents must stay clearly labeled FICTIONAL / DEMO.
- Legal-category copy must keep the qualified-professional disclaimer.
- Tests must stay green. Add coverage for new routes.

## Pull requests

1. Open an issue first for taxonomy or protocol changes (see `.github/ISSUE_TEMPLATE`).
2. Include tests.
3. Run `ruff check src tests scripts` and `pytest`.
