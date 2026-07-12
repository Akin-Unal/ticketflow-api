from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import GUID, BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class TicketStatus(StrEnum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_FOR_CUSTOMER = "WAITING_FOR_CUSTOMER"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class TicketPriority(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class TicketCategory(StrEnum):
    TECHNICAL = "TECHNICAL"
    BILLING = "BILLING"
    ACCOUNT = "ACCOUNT"
    FEATURE_REQUEST = "FEATURE_REQUEST"
    OTHER = "OTHER"


class TicketHistoryEvent(StrEnum):
    TICKET_CREATED = "TICKET_CREATED"
    STATUS_CHANGED = "STATUS_CHANGED"
    PRIORITY_CHANGED = "PRIORITY_CHANGED"
    ASSIGNEE_CHANGED = "ASSIGNEE_CHANGED"
    COMMENT_ADDED = "COMMENT_ADDED"
    TICKET_UPDATED = "TICKET_UPDATED"


class Ticket(BaseModel):
    __tablename__ = "tickets"
    __table_args__ = (
        Index("ix_tickets_status", "status"),
        Index("ix_tickets_priority", "priority"),
        Index("ix_tickets_category", "category"),
        Index("ix_tickets_created_by_id", "created_by_id"),
        Index("ix_tickets_assigned_to_id", "assigned_to_id"),
        Index("ix_tickets_created_at", "created_at"),
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus, native_enum=False),
        default=TicketStatus.OPEN,
        nullable=False,
    )
    priority: Mapped[TicketPriority] = mapped_column(
        Enum(TicketPriority, native_enum=False),
        default=TicketPriority.MEDIUM,
        nullable=False,
    )
    category: Mapped[TicketCategory] = mapped_column(
        Enum(TicketCategory, native_enum=False),
        default=TicketCategory.OTHER,
        nullable=False,
    )
    created_by_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    assigned_to_id: Mapped[UUID | None] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    creator: Mapped[User] = relationship(
        "User",
        back_populates="created_tickets",
        foreign_keys=[created_by_id],
    )
    assignee: Mapped[User | None] = relationship(
        "User",
        back_populates="assigned_tickets",
        foreign_keys=[assigned_to_id],
    )
    comments: Mapped[list[TicketComment]] = relationship(
        "TicketComment",
        back_populates="ticket",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TicketComment.created_at",
    )
    history: Mapped[list[TicketHistory]] = relationship(
        "TicketHistory",
        back_populates="ticket",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TicketHistory.created_at",
    )


class TicketComment(BaseModel):
    __tablename__ = "ticket_comments"

    ticket_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    ticket: Mapped[Ticket] = relationship("Ticket", back_populates="comments")
    author: Mapped[User] = relationship("User", back_populates="ticket_comments")


class TicketHistory(BaseModel):
    __tablename__ = "ticket_history"

    ticket_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    changed_by_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[TicketHistoryEvent] = mapped_column(
        Enum(TicketHistoryEvent, native_enum=False),
        nullable=False,
    )
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    ticket: Mapped[Ticket] = relationship("Ticket", back_populates="history")
    changed_by: Mapped[User] = relationship("User", back_populates="ticket_history_entries")
