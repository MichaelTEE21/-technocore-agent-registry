"""python -m tar_cli  —  register, profile, lookup, proof, capabilities, discover, task, verify, contributions, swarm."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

DEFAULT_BASE = os.environ.get("REGISTRY_URL", "http://127.0.0.1:8080")


def _headers() -> dict[str, str]:
    token = os.environ.get("REGISTRY_TOKEN")
    headers = {"Accept": "application/json"}
    if token:
        headers["X-Registry-Token"] = token
    return headers


def _client(url: str) -> httpx.Client:
    return httpx.Client(base_url=url, headers=_headers(), timeout=15.0)


def _print(data) -> None:
    print(json.dumps(data, indent=2, default=str))


def _die(resp: httpx.Response) -> None:
    try:
        body = resp.json()
    except Exception:
        body = {"error": {"code": "http_error", "message": resp.text[:400]}}
    _print(body)
    raise SystemExit(1 if resp.status_code >= 400 else 0)


def _ok(resp: httpx.Response):
    if resp.status_code >= 400:
        _die(resp)
    _print(resp.json())


def _iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sign(args, *, message_id: str, type: str, from_agent: str, to_agent: str, task_id: str | None, payload: dict) -> str | None:
    key_file = getattr(args, "key_file", None)
    if not key_file:
        return None
    path = Path(key_file)
    raw = path.read_bytes()
    if len(raw) == 64:
        try:
            raw = bytes.fromhex(raw.decode().strip())
        except Exception:
            pass
    if len(raw) != 32:
        print("error: key file must be 32 raw bytes or 64 hex chars", file=sys.stderr)
        raise SystemExit(2)
    from tar.crypto import canonical_message_bytes, sign

    msg = canonical_message_bytes(
        message_id=message_id,
        type=type,
        from_agent=from_agent,
        to_agent=to_agent,
        timestamp=_iso() if not getattr(args, "timestamp", None) else args.timestamp,
        task_id=task_id,
        payload=payload,
    )
    return sign(raw, msg)


def cmd_register(args: argparse.Namespace) -> None:
    path = Path(args.file)
    payload = json.loads(path.read_text(encoding="utf-8"))
    with _client(args.url) as client:
        _ok(client.post("/agents", json=payload))


def cmd_profile(args: argparse.Namespace) -> None:
    with _client(args.url) as client:
        _ok(client.get(f"/agents/{args.agent_id}"))


def cmd_lookup(args: argparse.Namespace) -> None:
    with _client(args.url) as client:
        _ok(client.get("/lookup", params={"did": args.did}))


def cmd_proof(args: argparse.Namespace) -> None:
    with _client(args.url) as client:
        _ok(client.get("/proof", params={"did": args.did}))


def cmd_capabilities(_args: argparse.Namespace) -> None:
    with _client(_args.url) as client:
        _ok(client.get("/capabilities"))


def cmd_discover(args: argparse.Namespace) -> None:
    caps = args.capability
    if isinstance(caps, str):
        caps = [caps]
    params = [("capability", c) for c in caps]
    with _client(args.url) as client:
        _ok(client.get("/discover", params=params))


def cmd_verify(args: argparse.Namespace) -> None:
    body = {"kind": args.kind, "summary": args.summary or ""}
    if args.evidence:
        body["evidence_uri"] = args.evidence
    if getattr(args, "capability", None):
        body["capability_id"] = args.capability
    if getattr(args, "checker", None):
        body["checker_id"] = args.checker
    with _client(args.url) as client:
        _ok(client.post(f"/agents/{args.agent_id}/verification", json=body))


def cmd_contributions(args: argparse.Namespace) -> None:
    params = {}
    if args.agent:
        params["agent"] = args.agent
    with _client(args.url) as client:
        _ok(client.get("/contributions", params=params or None))


def cmd_swarm(args: argparse.Namespace) -> None:
    caps = args.capability
    if isinstance(caps, str):
        caps = [caps]
    params = [("capability", c) for c in caps]
    with _client(args.url) as client:
        _ok(client.get("/swarms/assemble", params=params))


def cmd_task_create(args: argparse.Namespace) -> None:
    body = {
        "requester": args.requester,
        "requested_capability": args.capability,
        "description": args.description or "",
    }
    if args.assignee:
        body["assignee"] = args.assignee
    with _client(args.url) as client:
        _ok(client.post("/tasks", json=body))


def cmd_task_accept(args: argparse.Namespace) -> None:
    _task_action(args, "accept")


def cmd_task_result(args: argparse.Namespace) -> None:
    _task_action(args, "result")


def _task_action(args: argparse.Namespace, action: str) -> None:
    import uuid

    message_id = f"cli-{uuid.uuid4().hex[:10]}"
    timestamp = _iso()
    payload: dict = {}
    result = None
    if action == "result":
        if args.result:
            try:
                result = json.loads(args.result)
            except json.JSONDecodeError:
                result = {"text": args.result}
            payload["result"] = result
    with _client(args.url) as client:
        task = client.get(f"/tasks/{args.task_id}")
        if task.status_code >= 400:
            _die(task)
        t = task.json()
        to_agent = t.get("requester") or args.agent
        sig = _sign(
            args,
            message_id=message_id,
            type=action.upper() if action != "result" else "RESULT",
            from_agent=args.agent,
            to_agent=to_agent,
            task_id=args.task_id,
            payload=payload,
        )
        body = {
            "agent_id": args.agent,
            "message_id": message_id,
            "timestamp": timestamp,
            "payload": payload,
        }
        if sig:
            body["signature"] = sig
        if result is not None:
            body["result"] = result
        _ok(client.post(f"/tasks/{args.task_id}/{action}", json=body))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="technocore-agent",
        description=(
            "Local client for the Technocore Agent Registry. "
            "Discover agents by capability, delegate tasks, verify signatures. "
            "Not a live network."
        ),
    )
    p.add_argument("--url", default=DEFAULT_BASE, help="Registry base URL (or REGISTRY_URL)")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("register", help="POST an agent profile JSON file")
    r.add_argument("file", help="Path to agent JSON (public profile only — no private keys)")
    r.set_defaults(func=cmd_register)

    pr = sub.add_parser("profile", help="GET one agent profile")
    pr.add_argument("agent_id")
    pr.set_defaults(func=cmd_profile)

    lu = sub.add_parser("lookup", help="Look up a public DID in this local registry")
    lu.add_argument("did", help="Public DID (did:key:... or did:example:...). Never a private key.")
    lu.set_defaults(func=cmd_lookup)

    pf = sub.add_parser("proof", help="Print a public-profile proof snapshot (JSON; never keys)")
    pf.add_argument("did", help="Public DID. Never a private key.")
    pf.set_defaults(func=cmd_proof)

    c = sub.add_parser("capabilities", help="List taxonomy")
    c.set_defaults(func=cmd_capabilities)

    d = sub.add_parser("discover", help="Rank agents for one or more capabilities")
    d.add_argument("capability", nargs="+", help="Capability id(s)")
    d.set_defaults(func=cmd_discover)

    v = sub.add_parser("verify", help="Record claim/evidence/independent-check/vouch/dispute (does not auto-verify)")
    v.add_argument("agent_id")
    v.add_argument(
        "--kind",
        default="evidence",
        choices=["claim", "evidence", "dispute", "independently-checked", "vouch"],
    )
    v.add_argument("--summary", default="")
    v.add_argument("--evidence", default=None)
    v.add_argument("--capability", default=None)
    v.add_argument("--checker", default=None)
    v.set_defaults(func=cmd_verify)

    co = sub.add_parser("contributions", help="List contribution events (not a score)")
    co.add_argument("--agent", default=None)
    co.set_defaults(func=cmd_contributions)

    s = sub.add_parser("swarm", help="Propose a local swarm for capability(s)")
    s.add_argument("capability", nargs="+")
    s.set_defaults(func=cmd_swarm)

    sa = sub.add_parser("swarm-assemble", help="Alias for swarm")
    sa.add_argument("capability", nargs="+")
    sa.set_defaults(func=cmd_swarm)

    t = sub.add_parser("task", help="Create or progress a delegated task")
    tsub = t.add_subparsers(dest="task_cmd", required=True)
    tc = tsub.add_parser("create", help="Create a task")
    tc.add_argument("--requester", required=True)
    tc.add_argument("--capability", required=True)
    tc.add_argument("--description", default="")
    tc.add_argument("--assignee", default=None)
    tc.set_defaults(func=cmd_task_create)
    ta = tsub.add_parser("accept", help="Assignee accepts a task")
    ta.add_argument("task_id")
    ta.add_argument("--agent", required=True)
    ta.add_argument("--key-file", default=None, help="Gitignored 32-byte Ed25519 private key file")
    ta.set_defaults(func=cmd_task_accept)
    tr = tsub.add_parser("result", help="Assignee submits a result")
    tr.add_argument("task_id")
    tr.add_argument("--agent", required=True)
    tr.add_argument("--result", default='{"ok": true}')
    tr.add_argument("--key-file", default=None)
    tr.set_defaults(func=cmd_task_result)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
