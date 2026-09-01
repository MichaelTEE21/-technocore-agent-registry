"""SQLAlchemy models. SQLite by default; the session factory is Postgres-ready."""

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
    version: Mapped[str] = mapped_column(String(64), default="0.1.0")
    description: Mapped[str] = mapped_column(Text, default="")
    protocols_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(32), default="unknown", index=True)
    endpoint: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(32), default="claimed")
    fictional: Mapped[str] = mapped_column(String(8), default="true")
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


class AgentCapability(Base):
    __tablename__ = "agent_capabilities"
    __table_args__ = (UniqueConstraint("agent_id", "capability_id", name="uq_agent_cap"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"))
    capability_id: Mapped[str] = mapped_column(String(128), index=True)
    category: Mapped[str] = mapped_column(String(64), index=True)
    level: Mapped[str] = mapped_column(String(32), default="intermediate")

    agent: Mapped[Agent] = relationship(back_populates="capabilities")


class VerificationRecord(Base):
    __tablename__ = "verification_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32))  # claim | evidence | dispute
    status: Mapped[str] = mapped_column(String(32), default="claimed")
    summary: Mapped[str] = mapped_column(Text, default="")
    evidence_uri: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    agent: Mapped[Agent] = relationship(back_populates="verifications")


class ReputationEvent(Base):
    """Append-only event log. v0.1 stores events and does not compute a score."""

    __tablename__ = "reputation_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    agent: Mapped[Agent] = relationship(back_populates="reputation_events")


class Swarm(Base):
    """A named set of agent ids plus required capabilities.

    A swarm is how a group of agents is discovered and grouped by capability.
    Messaging and task delegation are FUTURE and are not implemented here.
    """

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

    swarm: Mapped[Swarm] = relationship(back_populates="members")
