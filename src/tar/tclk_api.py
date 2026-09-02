"""FastAPI routes for tclk rooms, transcript, and protocol state."""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from tar.db import get_db
from tar.security import error_body, require_registry_token
from tar.serialize import agent_to_out
from tar.tclk import (
    OFFER_ROOM_ID,
    TCLK_PROTOCOL,
    TCLK_RAIL_FLOP_HTLC,
    TclkError,
    agents_advertising_tclk,
    build_accept_via_bridge,
    build_offer_via_bridge,
    ensure_deal_room,
    ensure_offer_room,
    get_contract_state,
    list_transcript,
    post_frame,
    redact_secrets,
)
from tar.tclk_bridge import TclkBridgeError, generate_hash_lock, ping

router = APIRouter(prefix="/tclk", tags=["tclk"])
Db = Annotated[Session, Depends(get_db)]
Auth = Annotated[None, Depends(require_registry_token)]


class IgnoreExtras(BaseModel):
    model_config = ConfigDict(extra="ignore")


class TclkFramePost(IgnoreExtras):
    room_id: str = Field(default=OFFER_ROOM_ID, max_length=128)
    frame: dict[str, Any]
    signature: str | None = None
    agent_id: str | None = Field(default=None, max_length=128)


class TclkOfferBuild(IgnoreExtras):
    fields: dict[str, Any]


class TclkAcceptBuild(IgnoreExtras):
    offer: dict[str, Any]
    accept: dict[str, Any]


def _http(exc: TclkError) -> HTTPException:
    return HTTPException(
        status_code=exc.http_status,
        detail=error_body(exc.code, str(exc))["error"],
    )


def _entry_out(entry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "room_id": entry.room_id,
        "seq": entry.seq,
        "frame_type": entry.frame_type,
        "from_did": entry.from_did,
        "agent_id": entry.agent_id,
        "frame": redact_secrets(json.loads(entry.frame_json or "{}")),
        "line_text": entry.line_text,
        "signature": entry.signature,
        "signature_status": entry.signature_status,
        "contract_id": entry.contract_id,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }


def _contract_out(row) -> dict[str, Any]:
    try:
        state = redact_secrets(json.loads(row.state_json or "{}"))
    except json.JSONDecodeError:
        state = {}
    if isinstance(state, dict):
        state.pop("secret", None)
    return {
        "contract_id": row.contract_id,
        "offer_id": row.offer_id,
        "protocol_status": row.status,
        "settlement_status": row.settlement_status,
        "paper_only": row.paper_only == "true",
        "payer_did": row.payer_did,
        "payee_did": row.payee_did,
        "rail": row.rail,
        "rail_ref": row.rail_ref,
        "state": state,
        "note": (
            "protocol_status is derived from signed tclk frames via @flop-labs/tclk. "
            "settlement_status is independent — PaperRail is choreography only and "
            "never implies economic settlement or fund custody."
        ),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.get("/info")
def tclk_info(_: Auth):
    bridge = None
    bridge_error = None
    try:
        bridge = ping()
    except TclkBridgeError as exc:
        bridge_error = str(exc)
    return {
        "protocol": TCLK_PROTOCOL,
        "rails": [TCLK_RAIL_FLOP_HTLC, "paper", "x402"],
        "offer_room": OFFER_ROOM_ID,
        "bridge": bridge,
        "bridge_error": bridge_error,
        "custody": False,
        "settlement": "unverified_by_default",
        "disclaimer": (
            "Registry-mediated coordination only. Never custodies keys or funds. "
            "PaperRail is demo-only and settles nothing of value. "
            "Preimages are never logged or persisted."
        ),
    }


@router.get("/rooms")
def list_rooms(db: Db, _: Auth):
    from sqlalchemy import select

    from tar.models import TclkRoom

    ensure_offer_room(db)
    db.commit()
    rooms = list(db.scalars(select(TclkRoom).order_by(TclkRoom.id)))
    return {
        "items": [
            {
                "id": r.id,
                "kind": r.kind,
                "contract_id": r.contract_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rooms
        ]
    }


@router.get("/rooms/{room_id}/transcript")
def room_transcript(room_id: str, db: Db, _: Auth):
    ensure_offer_room(db)
    from tar.models import TclkRoom

    if db.get(TclkRoom, room_id) is None:
        raise HTTPException(
            status_code=404,
            detail=error_body("not_found", f"room not found: {room_id}")["error"],
        )
    entries = list_transcript(db, room_id)
    return {"room_id": room_id, "items": [_entry_out(e) for e in entries]}


@router.post("/rooms/{room_id}/frames", status_code=201)
def post_room_frame(room_id: str, body: TclkFramePost, db: Db, _: Auth):
    try:
        ensure_offer_room(db)
        if room_id != body.room_id and body.room_id:
            # path wins
            pass
        entry = post_frame(
            db,
            room_id=room_id,
            frame=body.frame,
            signature=body.signature,
            agent_id=body.agent_id,
        )
        db.commit()
        db.refresh(entry)
        return _entry_out(entry)
    except TclkError as exc:
        db.rollback()
        raise _http(exc) from exc


@router.get("/contracts/{contract_id}")
def contract_state(contract_id: str, db: Db, _: Auth):
    row = get_contract_state(db, contract_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=error_body("not_found", f"contract not found: {contract_id}")["error"],
        )
    return _contract_out(row)


@router.get("/state/{contract_id}")
def state_alias(contract_id: str, db: Db, _: Auth):
    """Alias for /contracts/{id} — protocol state with separate settlement flag."""
    row = get_contract_state(db, contract_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=error_body("not_found", f"contract not found: {contract_id}")["error"],
        )
    return _contract_out(row)


@router.get("/discover")
def discover_tclk_agents(db: Db, _: Auth):
    agents = agents_advertising_tclk(db)
    return {
        "protocol": TCLK_PROTOCOL,
        "rail_hint": TCLK_RAIL_FLOP_HTLC,
        "items": [
            {
                "agent": agent_to_out(a),
                "protocols": json.loads(a.protocols_json or "[]"),
            }
            for a in agents
        ],
        "note": (
            "Advertising tclk/1 or flop-htlc is a routing hint only — "
            "proof is a signed frame verifying against the agent DID/public_key."
        ),
    }


@router.post("/build/offer")
def api_build_offer(body: TclkOfferBuild, _: Auth):
    try:
        return {"offer": build_offer_via_bridge(body.fields)}
    except TclkError as exc:
        raise _http(exc) from exc


@router.post("/build/accept")
def api_build_accept(body: TclkAcceptBuild, _: Auth):
    try:
        return {"accept": build_accept_via_bridge(body.offer, body.accept)}
    except TclkError as exc:
        raise _http(exc) from exc


@router.post("/build/hash-lock")
def api_hash_lock(_: Auth):
    """Mint a hash lock. Preimage is returned once and must not be stored by the registry."""
    try:
        lock = generate_hash_lock()
    except TclkBridgeError as exc:
        raise HTTPException(
            status_code=503,
            detail=error_body("bridge_error", str(exc))["error"],
        ) from exc
    return {
        "hash": lock["hash"],
        "preimage": lock["preimage"],
        "warning": (
            "Ephemeral preimage for the client only. "
            "The registry does not log or persist preimages."
        ),
    }


@router.post("/rooms/deal/{contract_id}", status_code=201)
def create_deal_room(contract_id: str, db: Db, _: Auth):
    try:
        room = ensure_deal_room(db, contract_id)
        db.commit()
        return {
            "id": room.id,
            "kind": room.kind,
            "contract_id": room.contract_id,
        }
    except TclkError as exc:
        db.rollback()
        raise _http(exc) from exc
