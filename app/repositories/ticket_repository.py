from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models.ticket import (
    Ticket,
    TicketCategory,
    TicketComment,
    TicketHistory,
    TicketPriority,
    TicketStatus,
)
from app.repositories.base import BaseRepository


@dataclass(frozen=True)
class TicketFilters:
    status: TicketStatus | None = None
    priority: TicketPriority | None = None
    category: TicketCategory | None = None
    assigned_to_id: UUID | None = None
    created_by_id: UUID | None = None
    is_assigned: bool | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    q: str | None = None
    sort_by: str = "created_at"
    sort_dir: str = "desc"


class TicketRepository(BaseRepository[Ticket]):
    model = Ticket

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def list_tickets(
        self,
        filters: TicketFilters,
        offset: int,
        limit: int,
    ) -> tuple[list[Ticket], int]:
        statement = self._filtered_statement(filters)
        total = self.db.scalar(
            select(func.count()).select_from(statement.order_by(None).subquery())
        )
        order_column = getattr(Ticket, filters.sort_by)
        order_by = order_column.asc() if filters.sort_dir == "asc" else order_column.desc()
        rows = self.db.scalars(statement.order_by(order_by).offset(offset).limit(limit))
        return list(rows), total or 0

    def statistics(self, filters: TicketFilters) -> dict[str, object]:
        statement = self._filtered_statement(filters)
        total = self.db.scalar(select(func.count()).select_from(statement.subquery())) or 0
        assigned_filters = TicketFilters(**{**filters.__dict__, "is_assigned": True})
        assigned = (
            self.db.scalar(
                select(func.count()).select_from(
                    self._filtered_statement(assigned_filters).subquery()
                )
            )
            or 0
        )
        return {
            "total": total,
            "assigned": assigned,
            "unassigned": total - assigned,
            "by_status": self._count_by("status", TicketStatus, filters),
            "by_priority": self._count_by("priority", TicketPriority, filters),
            "by_category": self._count_by("category", TicketCategory, filters),
        }

    def list_comments(self, ticket_id: UUID, include_internal: bool) -> list[TicketComment]:
        statement = (
            select(TicketComment)
            .where(TicketComment.ticket_id == ticket_id)
            .order_by(TicketComment.created_at.asc())
        )
        if not include_internal:
            statement = statement.where(TicketComment.is_internal.is_(False))
        return list(self.db.scalars(statement))

    def list_history(self, ticket_id: UUID) -> list[TicketHistory]:
        statement = (
            select(TicketHistory)
            .where(TicketHistory.ticket_id == ticket_id)
            .order_by(TicketHistory.created_at.asc())
        )
        return list(self.db.scalars(statement))

    def save(self, item: Ticket | TicketComment | TicketHistory) -> None:
        self.db.add(item)

    def commit_and_refresh[T: Ticket | TicketComment](self, item: T) -> T:
        self.db.commit()
        self.db.refresh(item)
        return item

    def db_commit(self) -> None:
        self.db.commit()

    def _filtered_statement(self, filters: TicketFilters) -> Select[tuple[Ticket]]:
        statement = select(Ticket)
        if filters.status is not None:
            statement = statement.where(Ticket.status == filters.status)
        if filters.priority is not None:
            statement = statement.where(Ticket.priority == filters.priority)
        if filters.category is not None:
            statement = statement.where(Ticket.category == filters.category)
        if filters.assigned_to_id is not None:
            statement = statement.where(Ticket.assigned_to_id == filters.assigned_to_id)
        if filters.created_by_id is not None:
            statement = statement.where(Ticket.created_by_id == filters.created_by_id)
        if filters.is_assigned is True:
            statement = statement.where(Ticket.assigned_to_id.is_not(None))
        if filters.is_assigned is False:
            statement = statement.where(Ticket.assigned_to_id.is_(None))
        if filters.created_from is not None:
            statement = statement.where(Ticket.created_at >= filters.created_from)
        if filters.created_to is not None:
            statement = statement.where(Ticket.created_at <= filters.created_to)
        if filters.q:
            pattern = f"%{filters.q.strip()}%"
            statement = statement.where(
                or_(Ticket.title.ilike(pattern), Ticket.description.ilike(pattern))
            )
        return statement

    def _count_by[T: StrEnum](
        self,
        column_name: str,
        enum_type: type[T],
        filters: TicketFilters,
    ) -> dict[T, int]:
        statement = self._filtered_statement(filters).subquery()
        column = statement.c[column_name]
        count_statement = select(column, func.count()).group_by(column)
        counts = {row[0]: row[1] for row in self.db.execute(count_statement)}
        return {item: counts.get(item.value, counts.get(item, 0)) for item in enum_type}
