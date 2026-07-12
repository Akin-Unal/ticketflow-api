from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_active_user
from app.api.dependencies.database import get_database_session
from app.models.ticket import TicketCategory, TicketPriority, TicketStatus
from app.models.user import User
from app.repositories.ticket_repository import TicketFilters
from app.schemas.common import PaginatedResponse
from app.schemas.ticket import (
    TicketAdminUpdate,
    TicketAssigneeUpdate,
    TicketCategoryUpdate,
    TicketCommentCreate,
    TicketCommentRead,
    TicketCreate,
    TicketHistoryRead,
    TicketPriorityUpdate,
    TicketRead,
    TicketStatistics,
    TicketStatusUpdate,
)
from app.services.ticket_service import TicketService
from app.utils.pagination import PaginationParams, get_pagination_params

router = APIRouter(prefix="/tickets", tags=["tickets"])


def get_ticket_filters(
    status: TicketStatus | None = None,
    priority: TicketPriority | None = None,
    category: TicketCategory | None = None,
    assigned_to_id: UUID | None = None,
    created_by_id: UUID | None = None,
    is_assigned: bool | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    q: str | None = Query(default=None, min_length=1),
    sort_by: Literal["created_at", "updated_at", "priority", "status"] = "created_at",
    sort_dir: Literal["asc", "desc"] = "desc",
) -> TicketFilters:
    return TicketFilters(
        status=status,
        priority=priority,
        category=category,
        assigned_to_id=assigned_to_id,
        created_by_id=created_by_id,
        is_assigned=is_assigned,
        created_from=created_from,
        created_to=created_to,
        q=q,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@router.post(
    "",
    response_model=TicketRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create ticket",
)
def create_ticket(
    payload: TicketCreate,
    db: Annotated[Session, Depends(get_database_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> TicketRead:
    ticket = TicketService(db).create_ticket(payload, current_user)
    return TicketRead.model_validate(ticket)


@router.get(
    "",
    response_model=PaginatedResponse[TicketRead],
    summary="List tickets",
)
def list_tickets(
    params: Annotated[PaginationParams, Depends(get_pagination_params)],
    filters: Annotated[TicketFilters, Depends(get_ticket_filters)],
    db: Annotated[Session, Depends(get_database_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> PaginatedResponse[TicketRead]:
    return TicketService(db).list_tickets(filters, params, current_user)


@router.get(
    "/statistics",
    response_model=TicketStatistics,
    summary="Get ticket statistics",
)
def ticket_statistics(
    filters: Annotated[TicketFilters, Depends(get_ticket_filters)],
    db: Annotated[Session, Depends(get_database_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> TicketStatistics:
    return TicketService(db).statistics(filters, current_user)


@router.get(
    "/{ticket_id}",
    response_model=TicketRead,
    summary="Get ticket",
)
def get_ticket(
    ticket_id: UUID,
    db: Annotated[Session, Depends(get_database_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> TicketRead:
    ticket = TicketService(db).get_ticket(ticket_id, current_user)
    return TicketRead.model_validate(ticket)


@router.patch(
    "/{ticket_id}",
    response_model=TicketRead,
    summary="Update ticket details",
)
def update_ticket(
    ticket_id: UUID,
    payload: TicketAdminUpdate,
    db: Annotated[Session, Depends(get_database_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> TicketRead:
    ticket = TicketService(db).update_ticket(ticket_id, payload, current_user)
    return TicketRead.model_validate(ticket)


@router.patch(
    "/{ticket_id}/status",
    response_model=TicketRead,
    summary="Change ticket status",
)
def change_ticket_status(
    ticket_id: UUID,
    payload: TicketStatusUpdate,
    db: Annotated[Session, Depends(get_database_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> TicketRead:
    ticket = TicketService(db).change_status(ticket_id, payload.status, current_user)
    return TicketRead.model_validate(ticket)


@router.patch(
    "/{ticket_id}/priority",
    response_model=TicketRead,
    summary="Change ticket priority",
)
def change_ticket_priority(
    ticket_id: UUID,
    payload: TicketPriorityUpdate,
    db: Annotated[Session, Depends(get_database_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> TicketRead:
    ticket = TicketService(db).change_priority(ticket_id, payload.priority, current_user)
    return TicketRead.model_validate(ticket)


@router.patch(
    "/{ticket_id}/category",
    response_model=TicketRead,
    summary="Change ticket category",
)
def change_ticket_category(
    ticket_id: UUID,
    payload: TicketCategoryUpdate,
    db: Annotated[Session, Depends(get_database_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> TicketRead:
    ticket = TicketService(db).change_category(ticket_id, payload.category, current_user)
    return TicketRead.model_validate(ticket)


@router.patch(
    "/{ticket_id}/assignee",
    response_model=TicketRead,
    summary="Assign ticket",
)
def change_ticket_assignee(
    ticket_id: UUID,
    payload: TicketAssigneeUpdate,
    db: Annotated[Session, Depends(get_database_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> TicketRead:
    ticket = TicketService(db).change_assignee(ticket_id, payload.assigned_to_id, current_user)
    return TicketRead.model_validate(ticket)


@router.post(
    "/{ticket_id}/comments",
    response_model=TicketCommentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add ticket comment",
)
def add_ticket_comment(
    ticket_id: UUID,
    payload: TicketCommentCreate,
    db: Annotated[Session, Depends(get_database_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> TicketCommentRead:
    return TicketCommentRead.model_validate(
        TicketService(db).add_comment(ticket_id, payload, current_user)
    )


@router.get(
    "/{ticket_id}/comments",
    response_model=list[TicketCommentRead],
    summary="List ticket comments",
)
def list_ticket_comments(
    ticket_id: UUID,
    db: Annotated[Session, Depends(get_database_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> list[TicketCommentRead]:
    return TicketService(db).list_comments(ticket_id, current_user)


@router.get(
    "/{ticket_id}/history",
    response_model=list[TicketHistoryRead],
    summary="List ticket history",
)
def list_ticket_history(
    ticket_id: UUID,
    db: Annotated[Session, Depends(get_database_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> list[TicketHistoryRead]:
    return TicketService(db).list_history(ticket_id, current_user)
