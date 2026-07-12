from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel

if TYPE_CHECKING:
    from app.models.ticket import Ticket, TicketComment, TicketHistory


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    USER = "USER"


class User(BaseModel):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False),
        default=UserRole.USER,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_tickets: Mapped[list[Ticket]] = relationship(
        "Ticket",
        back_populates="creator",
        foreign_keys="Ticket.created_by_id",
    )
    assigned_tickets: Mapped[list[Ticket]] = relationship(
        "Ticket",
        back_populates="assignee",
        foreign_keys="Ticket.assigned_to_id",
    )
    ticket_comments: Mapped[list[TicketComment]] = relationship(
        "TicketComment",
        back_populates="author",
    )
    ticket_history_entries: Mapped[list[TicketHistory]] = relationship(
        "TicketHistory",
        back_populates="changed_by",
    )
