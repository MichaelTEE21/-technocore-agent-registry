"""Reputation event types. v0.1 stores events and does not compute a score."""

from __future__ import annotations

EVENT_TYPES = (
    "task_completed",
    "task_failed",
    "verification_success",
    "verification_failure",
    "community_endorsement",
    "dispute",
)

FUTURE_NOTE = (
    "A future release may derive a reputation score from these events. "
    "v0.1 is an append-only log with no scoring, ranking, or weighting."
)
