#!/usr/bin/env python3
"""Minimal httpx client against a running registry (python -m uvicorn tar.main:app)."""

from __future__ import annotations

import json
import os
import sys

import httpx

BASE = os.environ.get("REGISTRY_URL", "http://127.0.0.1:8080")


def main() -> int:
    capability = sys.argv[1] if len(sys.argv) > 1 else "crypto-research"
    with httpx.Client(base_url=BASE, timeout=10.0) as client:
        health = client.get("/healthz")
        health.raise_for_status()
        found = client.get("/agents", params={"capability": capability})
        found.raise_for_status()
        print(json.dumps(found.json(), indent=2))
        proposed = client.get("/swarms/assemble", params={"capability": capability})
        proposed.raise_for_status()
        print("--- proposed swarm ---")
        print(json.dumps(proposed.json(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
