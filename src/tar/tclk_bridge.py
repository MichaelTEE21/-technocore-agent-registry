"""Subprocess bridge to the real @flop-labs/tclk package."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_DEFAULT_BRIDGE = _REPO / "tclk-bridge" / "bin" / "tclk-bridge.mjs"
_SECRET_KEYS = frozenset({"preimage", "secret", "private_key", "privateKey"})


class TclkBridgeError(RuntimeError):
    def __init__(self, message: str, *, code: str = "bridge_error", detail: Any = None):
        super().__init__(message)
        self.code = code
        self.detail = detail


def _bridge_path() -> Path:
    override = os.environ.get("TCLK_BRIDGE_PATH")
    if override:
        return Path(override)
    return _DEFAULT_BRIDGE


def _redact_for_log(obj: Any) -> Any:
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if k in _SECRET_KEYS:
                out[k] = "[REDACTED]"
            else:
                out[k] = _redact_for_log(v)
        return out
    if isinstance(obj, list):
        return [_redact_for_log(x) for x in obj]
    return obj


def call_tclk(command: dict[str, Any], *, timeout: float = 30.0) -> Any:
    bridge = _bridge_path()
    if not bridge.is_file():
        raise TclkBridgeError(f"tclk bridge not found at {bridge}", code="bridge_missing")
    payload = json.dumps(command, separators=(",", ":"), ensure_ascii=True)
    try:
        proc = subprocess.run(
            ["node", str(bridge)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            cwd=str(bridge.parent.parent),
        )
    except FileNotFoundError as exc:
        raise TclkBridgeError("node runtime not found", code="node_missing") from exc
    except Exception as exc:
        if exc.__class__.__name__ == "TimeoutExpired":
            raise TclkBridgeError("tclk bridge timed out", code="bridge_timeout") from exc
        raise
    raw = (proc.stdout or "").strip()
    if not raw:
        err = (proc.stderr or "").strip() or f"exit {proc.returncode}"
        raise TclkBridgeError(f"empty bridge stdout: {err}", code="bridge_empty")
    try:
        body = json.loads(raw.splitlines()[-1])
    except json.JSONDecodeError as exc:
        raise TclkBridgeError("bridge returned non-JSON", code="bridge_bad_json") from exc
    if not body.get("ok"):
        raise TclkBridgeError(
            str(body.get("error") or "bridge error"),
            code=str(body.get("code") or "bridge_error"),
            detail=_redact_for_log(body),
        )
    return body.get("result")


def ping() -> dict[str, Any]:
    return call_tclk({"action": "ping"})


def make_offer(fields: dict[str, Any]) -> dict[str, Any]:
    return call_tclk({"action": "makeOffer", "fields": fields})


def make_accept(offer: dict[str, Any], accept: dict[str, Any]) -> dict[str, Any]:
    return call_tclk({"action": "makeAccept", "offer": offer, "accept": accept})


def generate_hash_lock() -> dict[str, Any]:
    """Mint a hash lock. Caller must treat preimage as ephemeral."""
    return call_tclk({"action": "generateHashLock"})


def open_contract(offer: dict[str, Any]) -> dict[str, Any]:
    return call_tclk({"action": "openContract", "offer": offer})


def apply_frame(
    state: dict[str, Any], frame: dict[str, Any], now_ms: int | None = None
) -> dict[str, Any]:
    cmd: dict[str, Any] = {"action": "applyFrame", "state": state, "frame": frame}
    if now_ms is not None:
        cmd["nowMs"] = now_ms
    return call_tclk(cmd)


def fold_transcript(
    offer: dict[str, Any],
    frames: list[dict[str, Any]],
    *,
    now_ms: int | None = None,
    stop_on_reject: bool = False,
) -> dict[str, Any]:
    cmd: dict[str, Any] = {
        "action": "foldTranscript",
        "offer": offer,
        "frames": frames,
        "stopOnReject": stop_on_reject,
    }
    if now_ms is not None:
        cmd["nowMs"] = now_ms
    return call_tclk(cmd)


def encode_frame(frame: dict[str, Any]) -> str:
    return call_tclk({"action": "encodeFrame", "frame": frame})["line"]


def try_decode_frame(text: str) -> dict[str, Any] | None:
    return call_tclk({"action": "tryDecodeFrame", "text": text})


def is_tclk_line(text: str) -> bool:
    return bool(call_tclk({"action": "isTclkLine", "text": text})["isTclk"])


def deal_room(contract: str) -> str:
    return call_tclk({"action": "dealRoom", "contract": contract})["room"]


def capability_token(rails: list[str]) -> str:
    return call_tclk({"action": "capabilityToken", "rails": rails})["token"]


def verify_hash_preimage(hash_hex: str, preimage: str) -> bool:
    return bool(
        call_tclk(
            {"action": "verifyHashPreimage", "hash": hash_hex, "preimage": preimage}
        )["valid"]
    )


def paper_lock(terms: dict[str, Any]) -> dict[str, Any]:
    """Demo only — PaperRail holds no value."""
    return call_tclk({"action": "paperLock", "terms": terms})


def paper_verify_lock(terms: dict[str, Any], ref: str) -> dict[str, Any]:
    return call_tclk({"action": "paperVerifyLock", "terms": terms, "ref": ref})


def lock_terms(state: dict[str, Any]) -> dict[str, Any]:
    return call_tclk({"action": "lockTerms", "state": state})
