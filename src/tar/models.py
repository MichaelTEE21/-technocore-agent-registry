"""SQLAlchemy models. SQLite by default; the session factory is Postgres-ready.

Tables: agents, capabilities, agent_capabilities, verification_records,
tasks, task_events, messages, contributions — plus swarms and a legacy
reputation_events log. Private keys are never stored.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    did: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    version: Mapped[str] = mapped_column(String(64), default="1.0.0")
    description: Mapped[str] = mapped_column(Text, default="")
    protocols_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(32), default="unknown", index=True)
    endpoint: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(32), default="claimed")
    public_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    fictional: Mapped[str] = mapped_column(String(8), default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    capabilities: Mapped[list[AgentCapability]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )
    verifications: Mapped[list[VerificationRecord]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )
    reputation_events: Mapped[list[ReputationEvent]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )
    contributions: Mapped[list[Contribution]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )


class Capability(Base):
    """Catalog row synced from the data-driven taxonomy. Not agent claims."""

    __tablename__ = "capabilities"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    category: Mapped[str] = mapped_column(String(64), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    disclaimer: Mapped[str | None] = mapped_column(Text, nullable=True)


class AgentCapability(Base):
    __tablename__ = "agent_capabilities"
    __table_args__ = (UniqueConstraint("agent_id", "capability_id", name="uq_agent_cap"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"))
    capability_id: Mapped[str] = mapped_column(String(128), index=True)
    category: Mapped[str] = mapped_column(String(64), index=True)
    level: Mapped[str] = mapped_column(String(32), default="intermediate")
    evidence_status: Mapped[str] = mapped_column(String(32), default="claimed", server_default="claimed")

    agent: Mapped[Agent] = relationship(back_populates="capabilities")


class VerificationRecord(Base):
    __tablename__ = "verification_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="claimed")
    summary: Mapped[str] = mapped_column(Text, default="")
    evidence_uri: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    capability_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    checker_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    agent: Mapped[Agent] = relationship(back_populates="verifications")


class ReputationEvent(Base):
    """Legacy append-only log. v1 records contributions instead of a score."""

    __tablename__ = "reputation_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    agent: Mapped[Agent] = relationship(back_populates="reputation_events")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    requester_id: Mapped[str] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    assignee_id: Mapped[str | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    requested_capability: Mapped[str] = mapped_column(String(128), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="requested", index=True)
    protocol: Mapped[str] = mapped_column(String(64), default="http")
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    events: Mapped[list[TaskEvent]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )


class TaskEvent(Base):
    __tablename__ = "task_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    event: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    task: Mapped[Task] = relationship(back_populates="events")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("message_id", name="uq_message_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    type: Mapped[str] = mapped_column(String(32), index=True)
    from_agent: Mapped[str] = mapped_column(String(128), index=True)
    to_agent: Mapped[str] = mapped_column(String(128), index=True)
    timestamp: Mapped[str] = mapped_column(String(64))
    task_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Contribution(Base):
    """Append-only contribution record. No money, no tokenomics, no score."""

    __tablename__ = "contributions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    event: Mapped[str] = mapped_column(String(64), index=True)
    task_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    reference: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    verification_state: Mapped[str] = mapped_column(String(32), default="claimed")
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    agent: Mapped[Agent] = relationship(back_populates="contributions")


class Swarm(Base):
    """A named set of agent ids plus required capabilities. Local grouping only."""

    __tablename__ = "swarms"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text, default="")
    required_capabilities_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    members: Mapped[list[SwarmMember]] = relationship(
        back_populates="swarm", cascade="all, delete-orphan"
    )


class SwarmMember(Base):
    __tablename__ = "swarm_members"
    __table_args__ = (UniqueConstraint("swarm_id", "agent_id", name="uq_swarm_member"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    swarm_id: Mapped[str] = mapped_column(ForeignKey("swarms.id", ondelete="CASCADE"))
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(32), default="recommended", server_default="recommended")

    swarm: Mapped[Swarm] = relationship(back_populates="members")
