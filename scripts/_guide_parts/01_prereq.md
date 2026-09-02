## Prerequisites

### Runtime

- Python **3.12+** (3.13 is fine)
- Optional: Node **18+** only if you need the tclk bridge for build helpers
- Clone / copy of this repo

### Install (registry)

```bash
cd technocore-prod
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
mkdir -p data
python scripts/seed_demo.py
```

### Start locally

```bash
PYTHONPATH=src uvicorn tar.main:app --host 127.0.0.1 --port 8765
```

Open http://127.0.0.1:8765/ . OpenAPI: /docs . Health: /healthz .

### Production / deployment URL

vercel.json configures a Vercel Python build (api/index.py). No fixed production hostname is published in README or config. Use **your deployment URL**, or http://127.0.0.1:8765 for local work. BASE means that URL in examples.

### Auth

- If REGISTRY_TOKEN is unset, mutating routes are open (local demo).
- If REGISTRY_TOKEN is set, send header X-Registry-Token on mutating routes.

