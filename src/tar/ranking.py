"""Transparent discovery ranking. No AI quality scores."""

from __future__ import annotations

from typing import Any

from tar.models import Agent

# Documented weights. Sum of maxima = 100.
WEIGHTS = {
    "capability_match": 40.0,
    "verification_status": 20.0,
    "availability": 20.0,
    "compatibility": 10.0,
    "evidence": 10.0,
}

VERIFICATION_POINTS = {
    "vouched": 20.0,
    "independently-checked": 16.0,
    "community-verified": 14.0,
    "verified": 12.0,
    "claimed": 6.0,
    "expired": 2.0,
    "disputed": 0.0,
}

AVAILABILITY_POINTS = {
    "online": 20.0,
    "unknown": 12.0,
    "busy": 6.0,
    "offline": 0.0,
}

RANKING_DOC = {
    "description": (
        "Rank is a documented weighted sum, not an AI quality score and not a "
        "reputation score. Higher is a better match for the requested capabilities."
    ),
    "weights": WEIGHTS,
    "verification_points": VERIFICATION_POINTS,
    "availability_points": AVAILABILITY_POINTS,
    "compatibility": "10 if the agent lists the requested protocol (or none requested); else 0.",
    "evidence": "10 if any capability has evidence beyond a bare claim; else 0.",
    "capability_match": "40 * (matched requested capabilities / requested count).",
}


def _cap_ids(agent: Agent) -> set[str]:
    return {c.capability_id for c in agent.capabilities}


def _has_evidence(agent: Agent) -> bool:
    for cap in agent.capabilities:
        if getattr(cap, "evidence_status", "claimed") not in {"claimed", None, ""}:
            if cap.evidence_status != "claimed":
                return True
    return False


def score_agent(
    agent: Agent,
    requested: list[str],
    *,
    protocol: str | None = None,
) -> dict[str, Any]:
    caps = _cap_ids(agent)
    req = [c for c in requested if c]
    matched = [c for c in req if c in caps]
    match_frac = (len(matched) / len(req)) if req else 0.0
    cap_score = WEIGHTS["capability_match"] * match_frac
    ver_score = VERIFICATION_POINTS.get(agent.verification_status, 0.0)
    avail_score = AVAILABILITY_POINTS.get(agent.status, 0.0)
    protocols = []
    try:
        import json

        protocols = json.loads(agent.protocols_json or "[]")
    except Exception:
        protocols = []
    if protocol is None or protocol in protocols:
        compat = WEIGHTS["compatibility"]
    else:
        compat = 0.0
    evidence = WEIGHTS["evidence"] if _has_evidence(agent) else 0.0
    breakdown = {
        "capability_match": round(cap_score, 2),
        "verification_status": ver_score,
        "availability": avail_score,
        "compatibility": compat,
        "evidence": evidence,
    }
    total = round(sum(breakdown.values()), 2)
    return {
        "rank": total,
        "rank_breakdown": breakdown,
        "matched_capabilities": matched,
    }


def rank_agents(
    agents: list[Agent],
    requested: list[str],
    *,
    protocol: str | None = None,
) -> list[tuple[Agent, dict[str, Any]]]:
    scored = [(a, score_agent(a, requested, protocol=protocol)) for a in agents]
    scored.sort(key=lambda pair: (-pair[1]["rank"], pair[0].id))
    return scored
