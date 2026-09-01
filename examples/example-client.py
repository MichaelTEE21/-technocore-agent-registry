#!/usr/bin/env python3
"""Minimal client against a running registry (python -m uvicorn tar.main:app).

Library usage (PYTHONPATH=src; no private keys by default):

    from tar_client import TarClient
    client = TarClient("http://127.0.0.1:8080")
    client.connect("http://127.0.0.1:8080")
    ranked = client.discover(["crypto-research"])
    task = client.create_task(
        requester="test-research",
        requested_capability="pdf-analysis",
        assignee="test-document",
        description="DEMO",
    )
    client.accept(task["task_id"], "test-document")
    client.progress(task["task_id"], "test-document", payload={"pct": 50})
    client.result(task["task_id"], "test-document", result={"ok": True})
    envelope = client.get_message(MESSAGE_ID)
    checked = client.verify_message(envelope)  # tar.crypto; presence of signature is not proof

Optional signing: TarClient(..., key_file="data/keys/test-document.key") — same as the CLI.
Never print or log the key.
"""

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
    try:
        from tar_client import TarClient
    except ImportError:
        return 0
    tar = TarClient(BASE)
    print("--- tar.a2a client discover ---")
    print(json.dumps(tar.discover([capability]), indent=2, default=str))
    tar.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
