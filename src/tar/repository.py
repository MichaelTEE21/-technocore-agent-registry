"""Persistence boundary. SQLAlchemy today; swap the engine/session for Postgres."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from tar.models import Agent, Contribution, Message, Swarm, Task


class RegistryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_agent(self, agent_id: str) -> Agent | None:
        return self.db.scalar(
            select(Agent).options(selectinload(Agent.capabilities)).where(Agent.id == agent_id)
        )

    def list_agents(self) -> list[Agent]:
        return list(
            self.db.scalars(select(Agent).options(selectinload(Agent.capabilities)).order_by(Agent.id))
        )

    def get_task(self, task_id: str) -> Task | None:
        return self.db.get(Task, task_id)

    def list_tasks(self) -> list[Task]:
        return list(self.db.scalars(select(Task).order_by(Task.created_at.desc())))

    def list_messages(self, task_id: str | None = None) -> list[Message]:
        stmt = select(Message).order_by(Message.created_at.asc())
        if task_id:
            stmt = stmt.where(Message.task_id == task_id)
        return list(self.db.scalars(stmt))

    def list_contributions(self, agent_id: str | None = None) -> list[Contribution]:
        stmt = select(Contribution).order_by(Contribution.created_at.desc())
        if agent_id:
            stmt = stmt.where(Contribution.agent_id == agent_id)
        return list(self.db.scalars(stmt))

    def get_swarm(self, swarm_id: str) -> Swarm | None:
        return self.db.scalar(
            select(Swarm).options(selectinload(Swarm.members)).where(Swarm.id == swarm_id)
        )
