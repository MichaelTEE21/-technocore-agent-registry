"""Contribution / reputation *events*. v1.0 stores events and does not compute a score."""

from __future__ import annotations

EVENT_TYPES = (
    "task_completed",
    "task_failed",
    "result_verified",
    "capability_verified",
    "community_endorsement",
    "dispute",
    "verification_success",
    "verification_failure",
)

FUTURE_NOTE = (
    "A future release may derive a documented reputation idea from these events. "
    "v1.0.0 is an append-only contribution log with no scoring, ranking-as-quality, "
    "or professional-qualification claim."
)
