"""tclk/1 rooms, signature auth, protocol advertising — registry-mediated.

Coordination only. Settlement rails (including PaperRail demo) never custody
keys or funds in this registry. Preimages are never logged or persisted.
Protocol state and settlement verification are tracked separately.
"""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tar.crypto import (
    SignatureError,
    resolve_verify_key,
    verify,
)
from tar.models import Agent, TclkContract, TclkRoom, TclkTranscript, utcnow
from tar.tclk_bridge import (
    TclkBridgeError,
    apply_frame,
    deal_room,
    encode_frame,
    fold_transcript,
    make_accept,
    make_offer,
    open_contract,
    try_decode_frame,
)

TCLK_PROTOCOL = "tclk/1"
TCLK_RAIL_FLOP_HTLC = "flop-htlc"
TCLK_RAIL_PAPER = "paper"
OFFER_ROOM_ID = "tclk-offers"

# Advertised protocol / rail tokens agents may list in Agent.protocols
KNOWN_TCLK_PROTOCOLS = (TCLK_PROTOCOL, TCLK_RAIL_FLOP_HTLC, TCLK_RAIL_PAPER, "x402")

_SECRET_FIELD = re.compile(r'"(preimage|secret)"\s*:\s*"[^"]*"', re.IGNORECASE)


class TclkError(ValueError):
    def __init__(self, code: str, message: str, http_status: int = 400):
        super().__init__(message)
        self.code = code
        self.http_status = http_status


def redact_secrets(obj: Any) -> Any:
    """Drop preimage/secret values from any structure before persistence."""
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if k in {"preimage", "secret", "private_key", "privateKey"}:
                out[k] = "[REDACTED]"
            else:
                out[k] = redact_secrets(v)
        return out
    if isinstance(obj, list):
        return [redact_secrets(x) for x in obj]
    if isinstance(obj, str):
        return _SECRET_FIELD.sub(r'"\1":"[REDACTED]"', obj)
    return obj


def canonical_frame_bytes(frame: dict[str, Any]) -> bytes:
    """Bytes signed by the agent for a posted frame (signature field excluded)."""
    body = {k: v for k, v in frame.items() if k != "signature"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def verify_frame_signature(
    db: Session,
    *,
    from_did: str,
    frame: dict[str, Any],
    signature_hex: str | None,
) -> str:
    """Return signature_status: valid | invalid | unsigned | no_key."""
    if not signature_hex:
        return "unsigned"
    agent = db.scalar(select(Agent).where(Agent.did == from_did))
    pub_hex = agent.public_key if agent else None
    try:
        key = resolve_verify_key(from_did, pub_hex)
    except SignatureError:
        return "invalid"
    if key is None:
        return "no_key"
    if verify(key, canonical_frame_bytes(frame), signature_hex):
        return "valid"
    return "invalid"


def ensure_offer_room(db: Session) -> TclkRoom:
    room = db.get(TclkRoom, OFFER_ROOM_ID)
    if room is None:
        room = TclkRoom(id=OFFER_ROOM_ID, kind="offers", contract_id=None)
        db.add(room)
        db.flush()
    return room


def ensure_deal_room(db: Session, contract_id: str) -> TclkRoom:
    try:
        room_id = deal_room(contract_id)
    except TclkBridgeError as exc:
        raise TclkError("bridge_error", str(exc), http_status=503) from exc
    room = db.get(TclkRoom, room_id)
    if room is None:
        room = TclkRoom(id=room_id, kind="deal", contract_id=contract_id)
        db.add(room)
        db.flush()
    return room


def _next_seq(db: Session, room_id: str) -> int:
    current = db.scalar(
        select(func.coalesce(func.max(TclkTranscript.seq), 0)).where(
            TclkTranscript.room_id == room_id
        )
    )
    return int(current or 0) + 1


def _upsert_contract_from_state(
    db: Session,
    *,
    state: dict[str, Any],
    offer: dict[str, Any] | None = None,
) -> TclkContract | None:
    contract_id = state.get("contract")
    if not contract_id:
        # proposed: key by offer id until accept
        offer_id = (offer or state.get("offer") or {}).get("id")
        if not offer_id:
            return None
        row = db.scalar(select(TclkContract).where(TclkContract.offer_id == offer_id))
        if row is None:
            row = TclkContract(
                contract_id=f"offer:{offer_id}",
                offer_id=offer_id,
                status=state.get("status") or "proposed",
                state_json=json.dumps(redact_secrets(state), separators=(",", ":")),
                payer_did=state.get("payerDid"),
                payee_did=state.get("payeeDid"),
                settlement_status="unverified",
                paper_only="true",
            )
            db.add(row)
        else:
            row.status = state.get("status") or row.status
            row.state_json = json.dumps(redact_secrets(state), separators=(",", ":"))
            row.payer_did = state.get("payerDid") or row.payer_did
            row.payee_did = state.get("payeeDid") or row.payee_did
            row.updated_at = utcnow()
        return row

    row = db.get(TclkContract, contract_id)
    public_state = redact_secrets(state)
    # Never persist secret even if machine returned one
    if isinstance(public_state, dict):
        public_state.pop("secret", None)
    if row is None:
        row = TclkContract(
            contract_id=contract_id,
            offer_id=(offer or state.get("offer") or {}).get("id"),
            status=state.get("status") or "proposed",
            state_json=json.dumps(public_state, separators=(",", ":")),
            payer_did=state.get("payerDid"),
            payee_did=state.get("payeeDid"),
            rail=state.get("rail"),
            rail_ref=state.get("railRef"),
            settlement_status="unverified",
            paper_only="true" if state.get("rail") in {None, "paper", "memory-demo"} else "false",
        )
        db.add(row)
    else:
        row.status = state.get("status") or row.status
        row.state_json = json.dumps(public_state, separators=(",", ":"))
        row.payer_did = state.get("payerDid") or row.payer_did
        row.payee_did = state.get("payeeDid") or row.payee_did
        row.rail = state.get("rail") or row.rail
        row.rail_ref = state.get("railRef") or row.rail_ref
        row.updated_at = utcnow()
        # Settlement stays unverified unless explicitly paper-demo marked
        if row.rail in {"paper", "memory-demo"}:
            row.paper_only = "true"
            row.settlement_status = "unverified"
    return row


def post_frame(
    db: Session,
    *,
    room_id: str,
    frame: dict[str, Any],
    signature: str | None = None,
    agent_id: str | None = None,
    line_text: str | None = None,
) -> TclkTranscript:
    """Append a frame to a room transcript; fold protocol state via real tclk machine."""
    ensure_offer_room(db)
    room = db.get(TclkRoom, room_id)
    if room is None:
        raise TclkError("not_found", f"room not found: {room_id}", http_status=404)

    frame_type = frame.get("type")
    if not frame_type:
        raise TclkError("validation_error", "frame.type is required")

    from_did = frame.get("from")
    if not from_did or not isinstance(from_did, str):
        raise TclkError("validation_error", "frame.from DID is required")

    # Reject attempts to persist raw secrets server-side
    if frame_type == "reveal" and frame.get("secret"):
        # Allow verify-path: apply in-memory via bridge, store redacted only
        pass

    sig_status = verify_frame_signature(
        db, from_did=from_did, frame=frame, signature_hex=signature
    )

    safe_frame = redact_secrets(dict(frame))
    line = line_text or ""
    if frame_type == "reveal":
        # Never persist reveal lines or secret material.
        line = ""
        safe_frame = redact_secrets(dict(frame))
    elif not line:
        try:
            line = encode_frame(frame)
        except TclkBridgeError:
            line = ""

    contract_id = frame.get("contract") or (
        frame.get("id") if frame_type == "offer" else frame.get("ref")
    )

    entry = TclkTranscript(
        room_id=room_id,
        seq=_next_seq(db, room_id),
        frame_type=str(frame_type),
        from_did=from_did,
        agent_id=agent_id,
        frame_json=json.dumps(safe_frame, separators=(",", ":"), sort_keys=True),
        line_text=line[:4096] if line else None,
        signature=signature,
        signature_status=sig_status,
        contract_id=str(contract_id) if contract_id else None,
    )
    db.add(entry)
    db.flush()

    # Advance protocol state using the real machine (with original frame for verify)
    _advance_protocol(db, frame=frame, room=room)
    return entry


def _advance_protocol(db: Session, *, frame: dict[str, Any], room: TclkRoom) -> None:
    ftype = frame.get("type")
    try:
        if ftype == "offer":
            state = open_contract(frame)
            _upsert_contract_from_state(db, state=state, offer=frame)
            return

        if ftype == "accept":
            # Find offer in offer room by ref
            offer = _load_offer_frame(db, frame.get("ref"))
            if offer is None:
                return
            state = open_contract(offer)
            step = apply_frame(state, frame)
            if step.get("ok"):
                st = step["state"]
                _upsert_contract_from_state(db, state=st, offer=offer)
                if st.get("contract"):
                    ensure_deal_room(db, st["contract"])
            return

        contract_id = frame.get("contract")
        if not contract_id:
            return
        row = db.get(TclkContract, contract_id)
        if row is None:
            return
        state = json.loads(row.state_json)
        # Re-hydrate secret-less state; reveal needs secret only transiently
        step = apply_frame(state, frame)
        if step.get("ok"):
            _upsert_contract_from_state(db, state=step["state"])
    except TclkBridgeError:
        # Fail-closed for protocol advance; transcript line still stored
        return


def _load_offer_frame(db: Session, offer_id: str | None) -> dict[str, Any] | None:
    if not offer_id:
        return None
    rows = db.scalars(
        select(TclkTranscript)
        .where(TclkTranscript.frame_type == "offer")
        .order_by(TclkTranscript.seq.asc())
    )
    for row in rows:
        try:
            data = json.loads(row.frame_json)
        except json.JSONDecodeError:
            continue
        if data.get("id") == offer_id:
            return data
    return None


def list_transcript(db: Session, room_id: str) -> list[TclkTranscript]:
    return list(
        db.scalars(
            select(TclkTranscript)
            .where(TclkTranscript.room_id == room_id)
            .order_by(TclkTranscript.seq.asc(), TclkTranscript.id.asc())
        )
    )


def get_contract_state(db: Session, contract_id: str) -> TclkContract | None:
    return db.get(TclkContract, contract_id)


def agents_advertising_tclk(db: Session) -> list[Agent]:
    """Agents whose protocols include tclk/1 or flop-htlc (discovery hint only)."""
    agents = list(db.scalars(select(Agent).order_by(Agent.id)))
    out: list[Agent] = []
    for agent in agents:
        try:
            protocols = json.loads(agent.protocols_json or "[]")
        except json.JSONDecodeError:
            protocols = []
        if not isinstance(protocols, list):
            continue
        lowered = {str(p).strip().lower() for p in protocols}
        if "tclk/1" in lowered or "tclk1" in lowered or "flop-htlc" in lowered:
            out.append(agent)
    return out


def build_offer_via_bridge(fields: dict[str, Any]) -> dict[str, Any]:
    try:
        return make_offer(fields)
    except TclkBridgeError as exc:
        raise TclkError("bridge_error", str(exc), http_status=503) from exc


def build_accept_via_bridge(offer: dict[str, Any], accept: dict[str, Any]) -> dict[str, Any]:
    try:
        return make_accept(offer, accept)
    except TclkBridgeError as exc:
        raise TclkError("bridge_error", str(exc), http_status=503) from exc


def recompute_state_from_transcript(db: Session, contract_id: str) -> dict[str, Any]:
    """Fold stored frames through the real machine (secrets already redacted — reveal may fail)."""
    row = db.get(TclkContract, contract_id)
    if row is None:
        raise TclkError("not_found", f"contract not found: {contract_id}", http_status=404)
    offer = _load_offer_frame(db, row.offer_id)
    if offer is None and row.state_json:
        try:
            st = json.loads(row.state_json)
            offer = st.get("offer")
        except json.JSONDecodeError:
            offer = None
    if not offer:
        raise TclkError("validation_error", "offer frame missing for contract")
    frames: list[dict[str, Any]] = []
    for entry in list_transcript(db, deal_room(contract_id) if not contract_id.startswith("offer:") else OFFER_ROOM_ID):
        if entry.contract_id and entry.contract_id not in {contract_id, row.offer_id}:
            # include accepts that reference offer
            pass
        try:
            fr = json.loads(entry.frame_json)
        except json.JSONDecodeError:
            continue
        if fr.get("type") == "offer":
            continue
        if fr.get("type") == "reveal" and fr.get("secret") == "[REDACTED]":
            # Cannot re-verify claim without secret — leave state as stored
            continue
        frames.append(fr)
    try:
        return fold_transcript(offer, frames)
    except TclkBridgeError as exc:
        raise TclkError("bridge_error", str(exc), http_status=503) from exc


def decode_line(text: str) -> dict[str, Any] | None:
    try:
        return try_decode_frame(text)
    except TclkBridgeError as exc:
        raise TclkError("bridge_error", str(exc), http_status=503) from exc
