from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.ticket import (
    TicketCategory,
    TicketHistoryEvent,
    TicketPriority,
    TicketStatus,
)


class TicketCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200, examples=["Cannot access billing portal"])
    description: str = Field(min_length=1, examples=["The billing portal returns a 403 error."])
    priority: TicketPriority = TicketPriority.MEDIUM
    category: TicketCategory = TicketCategory.OTHER


class TicketUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1)


class TicketAdminUpdate(TicketUpdate):
    priority: TicketPriority | None = None
    category: TicketCategory | None = None


class TicketStatusUpdate(BaseModel):
    status: TicketStatus


class TicketPriorityUpdate(BaseModel):
    priority: TicketPriority


class TicketCategoryUpdate(BaseModel):
    category: TicketCategory


class TicketAssigneeUpdate(BaseModel):
    assigned_to_id: UUID | None = None


class TicketCommentCreate(BaseModel):
    content: str = Field(min_length=1, examples=["I can reproduce this on my account."])
    is_internal: bool = False


class TicketCommentRead(BaseModel):
    id: UUID
    ticket_id: UUID
    author_id: UUID
    content: str
    is_internal: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TicketHistoryRead(BaseModel):
    id: UUID
    ticket_id: UUID
    changed_by_id: UUID
    event_type: TicketHistoryEvent
    old_value: str | None
    new_value: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TicketRead(BaseModel):
    id: UUID
    title: str
    description: str
    status: TicketStatus
    priority: TicketPriority
    category: TicketCategory
    created_by_id: UUID
    assigned_to_id: UUID | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    closed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class TicketStatistics(BaseModel):
    total: int
    assigned: int
    unassigned: int
    by_status: dict[TicketStatus, int]
    by_priority: dict[TicketPriority, int]
    by_category: dict[TicketCategory, int]
