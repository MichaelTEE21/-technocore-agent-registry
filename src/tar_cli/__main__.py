"""python -m tar_cli  —  register, profile, capabilities, discover, verify, swarm-assemble."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

DEFAULT_BASE = os.environ.get("REGISTRY_URL", "http://127.0.0.1:8080")


def _headers() -> dict[str, str]:
    token = os.environ.get("REGISTRY_TOKEN")
    headers = {"Accept": "application/json"}
    if token:
        headers["X-Registry-Token"] = token
    return headers


def _client() -> httpx.Client:
    return httpx.Client(base_url=DEFAULT_BASE, headers=_headers(), timeout=15.0)


def _print(data) -> None:
    print(json.dumps(data, indent=2, default=str))


def _die(resp: httpx.Response) -> None:
    try:
        body = resp.json()
    except Exception:
        body = {"error": {"code": "http_error", "message": resp.text[:400]}}
    _print(body)
    raise SystemExit(1 if resp.status_code >= 400 else 0)


def cmd_register(args: argparse.Namespace) -> None:
    path = Path(args.file)
    payload = json.loads(path.read_text(encoding="utf-8"))
    with _client() as client:
        resp = client.post("/agents", json=payload)
    if resp.status_code >= 400:
        _die(resp)
    _print(resp.json())


def cmd_profile(args: argparse.Namespace) -> None:
    with _client() as client:
        resp = client.get(f"/agents/{args.agent_id}")
    if resp.status_code >= 400:
        _die(resp)
    _print(resp.json())


def cmd_capabilities(_args: argparse.Namespace) -> None:
    with _client() as client:
        resp = client.get("/capabilities")
    if resp.status_code >= 400:
        _die(resp)
    _print(resp.json())


def cmd_discover(args: argparse.Namespace) -> None:
    with _client() as client:
        resp = client.get("/agents", params={"capability": args.capability})
    if resp.status_code >= 400:
        _die(resp)
    _print(resp.json())


def cmd_verify(args: argparse.Namespace) -> None:
    body = {"kind": args.kind, "summary": args.summary or ""}
    if args.evidence:
        body["evidence_uri"] = args.evidence
    with _client() as client:
        resp = client.post(f"/agents/{args.agent_id}/verification", json=body)
    if resp.status_code >= 400:
        _die(resp)
    _print(resp.json())


def cmd_swarm_assemble(args: argparse.Namespace) -> None:
    with _client() as client:
        resp = client.get("/swarms/assemble", params={"capability": args.capability})
    if resp.status_code >= 400:
        _die(resp)
    _print(resp.json())


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="technocore-agent",
        description="Discover and group a swarm of agents by capability.",
    )
    p.add_argument("--url", default=DEFAULT_BASE, help="Registry base URL")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("register", help="POST an agent profile JSON file")
    r.add_argument("file", help="Path to agent JSON")
    r.set_defaults(func=cmd_register)

    pr = sub.add_parser("profile", help="GET one agent profile")
    pr.add_argument("agent_id")
    pr.set_defaults(func=cmd_profile)

    c = sub.add_parser("capabilities", help="List taxonomy")
    c.set_defaults(func=cmd_capabilities)

    d = sub.add_parser("discover", help="Find agents advertising a capability")
    d.add_argument("capability")
    d.set_defaults(func=cmd_discover)

    v = sub.add_parser("verify", help="Record a claim or evidence (does not auto-verify)")
    v.add_argument("agent_id")
    v.add_argument("--kind", default="evidence", choices=["claim", "evidence", "dispute"])
    v.add_argument("--summary", default="")
    v.add_argument("--evidence", default=None)
    v.set_defaults(func=cmd_verify)

    s = sub.add_parser("swarm-assemble", help="Propose a swarm for a capability")
    s.add_argument("capability")
    s.set_defaults(func=cmd_swarm_assemble)

    return p


def main(argv: list[str] | None = None) -> int:
    global DEFAULT_BASE
    parser = build_parser()
    args = parser.parse_args(argv)
    DEFAULT_BASE = args.url
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
