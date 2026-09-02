#!/usr/bin/env python3
"""ONE-SHOT MANUAL helper: update an agent's DID-derived public_key and fictional flag.

Does NOT run automatically. Does NOT touch production Neon unless you point
DATABASE_URL at it deliberately and confirm.

Example (local / staging only):

  DATABASE_URL=sqlite:///./data/registry.db \\
    python scripts/manual_fix_agent_pubkey.py \\
      --agent-id mananze-technocore-agent \\
      --did did:key:z6Mkrv5ZL3VsapUdVKirgFiJVdw7y5w8Bq3zDvmfNMDSAAep \\
      --fictional false \\
      --dry-run

Prefer PUT /agents/{id} via the API when the registry is running:

  curl -X PUT "$BASE/agents/mananze-technocore-agent" \\
    -H "Content-Type: application/json" \\
    -H "X-Registry-Token: $REGISTRY_TOKEN" \\
    -d '{"did":"did:key:z6Mkrv5ZL3VsapUdVKirgFiJVdw7y5w8Bq3zDvmfNMDSAAep","fictional":false}'

Never pass private keys. Public DID / public_key only.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tar.crypto import resolve_registration_public_key  # noqa: E402
from tar.db import get_session_factory, init_db  # noqa: E402
from tar.identity import default_identity_provider, is_demo_did  # noqa: E402
from tar.models import Agent, utcnow  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--did", default=None, help="Optional new public DID")
    parser.add_argument(
        "--fictional",
        choices=("true", "false"),
        default=None,
        help="Set fictional/demo flag",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned changes without writing",
    )
    parser.add_argument(
        "--i-understand-this-mutates-the-db",
        action="store_true",
        help="Required unless --dry-run",
    )
    args = parser.parse_args()

    if not args.dry_run and not args.i_understand_this_mutates_the_db:
        print(
            "Refusing to write: pass --dry-run or --i-understand-this-mutates-the-db",
            file=sys.stderr,
        )
        return 2

    init_db()
    db = get_session_factory()()
    try:
        agent = db.get(Agent, args.agent_id)
        if agent is None:
            print(f"agent not found: {args.agent_id}", file=sys.stderr)
            return 1
        new_did = agent.did
        if args.did:
            new_did = default_identity_provider.validate_public_did(args.did)
        new_pub = resolve_registration_public_key(new_did, None)
        if new_pub is None and agent.public_key:
            new_pub = agent.public_key
        fictional = agent.fictional
        if args.fictional is not None:
            if is_demo_did(new_did) and args.fictional == "false":
                print("did:example: cannot be non-fictional", file=sys.stderr)
                return 1
            fictional = args.fictional
        elif is_demo_did(new_did):
            fictional = "true"

        print(f"agent_id={agent.id}")
        print(f"did: {agent.did!r} -> {new_did!r}")
        print(f"public_key: {agent.public_key!r} -> {new_pub!r}")
        print(f"fictional: {agent.fictional!r} -> {fictional!r}")
        if args.dry_run:
            print("dry-run: no write")
            return 0
        agent.did = new_did
        agent.public_key = new_pub
        agent.fictional = fictional
        agent.updated_at = utcnow()
        db.commit()
        print("updated")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
