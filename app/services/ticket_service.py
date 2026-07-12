from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import (
    AuthorizationError,
    BusinessRuleError,
    InternalCommentForbiddenError,
    InvalidAssigneeError,
    InvalidStatusTransitionError,
    TicketAccessDeniedError,
    TicketClosedError,
    TicketNotFoundError,
)
from app.models.ticket import (
    Ticket,
    TicketCategory,
    TicketComment,
    TicketHistory,
    TicketHistoryEvent,
    TicketPriority,
    TicketStatus,
)
from app.models.user import User, UserRole
from app.repositories.ticket_repository import TicketFilters, TicketRepository
from app.repositories.user_repository import UserRepository
from app.schemas.common import PaginatedResponse
from app.schemas.ticket import (
    TicketAdminUpdate,
    TicketCommentCreate,
    TicketCommentRead,
    TicketCreate,
    TicketHistoryRead,
    TicketRead,
    TicketStatistics,
    TicketUpdate,
)
from app.utils.pagination import PaginationParams, total_pages

ADMIN_TRANSITIONS = {
    TicketStatus.OPEN: {TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED},
    TicketStatus.IN_PROGRESS: {TicketStatus.WAITING_FOR_CUSTOMER, TicketStatus.RESOLVED},
    TicketStatus.WAITING_FOR_CUSTOMER: {TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED},
    TicketStatus.RESOLVED: {TicketStatus.OPEN, TicketStatus.CLOSED},
    TicketStatus.CLOSED: {TicketStatus.OPEN},
}

USER_TRANSITIONS = {
    TicketStatus.RESOLVED: {TicketStatus.OPEN},
}


class TicketService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.tickets = TicketRepository(db)
        self.users = UserRepository(db)

    def create_ticket(self, payload: TicketCreate, actor: User) -> Ticket:
        ticket = Ticket(
            title=payload.title,
            description=payload.description,
            priority=payload.priority,
            category=payload.category,
            created_by_id=actor.id,
        )
        self.tickets.save(ticket)
        self._add_history(
            ticket=ticket,
            actor=actor,
            event_type=TicketHistoryEvent.TICKET_CREATED,
            old_value=None,
            new_value=TicketStatus.OPEN.value,
        )
        return self.tickets.commit_and_refresh(ticket)

    def list_tickets(
        self,
        filters: TicketFilters,
        params: PaginationParams,
        actor: User,
    ) -> PaginatedResponse[TicketRead]:
        filters = self._scope_filters(filters, actor)
        tickets, total = self.tickets.list_tickets(filters, params.offset, params.page_size)
        return PaginatedResponse[TicketRead](
            items=[TicketRead.model_validate(ticket) for ticket in tickets],
            page=params.page,
            page_size=params.page_size,
            total=total,
            total_pages=total_pages(total, params.page_size),
        )

    def get_ticket(self, ticket_id: UUID, actor: User) -> Ticket:
        ticket = self.tickets.get(ticket_id)
        if ticket is None:
            raise TicketNotFoundError()
        self._require_ticket_access(ticket, actor)
        return ticket

    def update_ticket(
        self,
        ticket_id: UUID,
        payload: TicketUpdate | TicketAdminUpdate,
        actor: User,
    ) -> Ticket:
        ticket = self.get_ticket(ticket_id, actor)
        self._require_not_closed(ticket)
        changed = False
        if actor.role != UserRole.ADMIN and ticket.status != TicketStatus.OPEN:
            raise BusinessRuleError("Normal users may only edit open tickets")
        if payload.title is not None and payload.title != ticket.title:
            self._add_history(
                ticket,
                actor,
                TicketHistoryEvent.TICKET_UPDATED,
                ticket.title,
                payload.title,
            )
            ticket.title = payload.title
            changed = True
        if payload.description is not None and payload.description != ticket.description:
            self._add_history(
                ticket,
                actor,
                TicketHistoryEvent.TICKET_UPDATED,
                ticket.description,
                payload.description,
            )
            ticket.description = payload.description
            changed = True
        if isinstance(payload, TicketAdminUpdate):
            includes_admin_fields = payload.priority is not None or payload.category is not None
            if actor.role != UserRole.ADMIN and includes_admin_fields:
                raise AuthorizationError("Only admins may update ticket metadata")
            if (
                actor.role == UserRole.ADMIN
                and payload.priority is not None
                and (payload.priority != ticket.priority)
            ):
                self._change_priority(ticket, payload.priority, actor)
                changed = True
            if (
                actor.role == UserRole.ADMIN
                and payload.category is not None
                and (payload.category != ticket.category)
            ):
                self._change_category(ticket, payload.category, actor)
                changed = True
        if changed:
            return self.tickets.commit_and_refresh(ticket)
        return ticket

    def change_status(self, ticket_id: UUID, status: TicketStatus, actor: User) -> Ticket:
        ticket = self.get_ticket(ticket_id, actor)
        if ticket.status == status:
            return ticket
        allowed = ADMIN_TRANSITIONS if actor.role == UserRole.ADMIN else USER_TRANSITIONS
        if status not in allowed.get(ticket.status, set()):
            raise InvalidStatusTransitionError(
                f"Cannot move ticket from {ticket.status} to {status}"
            )
        if actor.role != UserRole.ADMIN and ticket.created_by_id != actor.id:
            raise TicketAccessDeniedError()
        old_status = ticket.status
        ticket.status = status
        self._apply_status_timestamps(ticket, old_status, status)
        self._add_history(
            ticket,
            actor,
            TicketHistoryEvent.STATUS_CHANGED,
            old_status.value,
            status.value,
        )
        return self.tickets.commit_and_refresh(ticket)

    def change_priority(
        self,
        ticket_id: UUID,
        priority: TicketPriority,
        actor: User,
    ) -> Ticket:
        self._require_admin(actor)
        ticket = self.get_ticket(ticket_id, actor)
        self._require_not_closed(ticket)
        if priority != ticket.priority:
            self._change_priority(ticket, priority, actor)
            return self.tickets.commit_and_refresh(ticket)
        return ticket

    def change_category(
        self,
        ticket_id: UUID,
        category: TicketCategory,
        actor: User,
    ) -> Ticket:
        self._require_admin(actor)
        ticket = self.get_ticket(ticket_id, actor)
        self._require_not_closed(ticket)
        if category != ticket.category:
            self._change_category(ticket, category, actor)
            return self.tickets.commit_and_refresh(ticket)
        return ticket

    def change_assignee(
        self,
        ticket_id: UUID,
        assigned_to_id: UUID | None,
        actor: User,
    ) -> Ticket:
        self._require_admin(actor)
        ticket = self.get_ticket(ticket_id, actor)
        self._require_not_closed(ticket)
        assignee = None if assigned_to_id is None else self.users.get_by_id(assigned_to_id)
        if assigned_to_id is not None and (
            assignee is None or assignee.role != UserRole.ADMIN or not assignee.is_active
        ):
            raise InvalidAssigneeError()
        old_value = str(ticket.assigned_to_id) if ticket.assigned_to_id else None
        new_value = str(assigned_to_id) if assigned_to_id else None
        if old_value != new_value:
            ticket.assigned_to_id = assigned_to_id
            self._add_history(
                ticket,
                actor,
                TicketHistoryEvent.ASSIGNEE_CHANGED,
                old_value,
                new_value,
            )
            return self.tickets.commit_and_refresh(ticket)
        return ticket

    def add_comment(
        self,
        ticket_id: UUID,
        payload: TicketCommentCreate,
        actor: User,
    ) -> TicketComment:
        ticket = self.get_ticket(ticket_id, actor)
        self._require_not_closed(ticket)
        if payload.is_internal and actor.role != UserRole.ADMIN:
            raise InternalCommentForbiddenError()
        comment = TicketComment(
            ticket_id=ticket.id,
            author_id=actor.id,
            content=payload.content,
            is_internal=payload.is_internal,
        )
        self.tickets.save(comment)
        self._add_history(
            ticket,
            actor,
            TicketHistoryEvent.COMMENT_ADDED,
            None,
            "internal" if payload.is_internal else "public",
        )
        return self.tickets.commit_and_refresh(comment)

    def list_comments(self, ticket_id: UUID, actor: User) -> list[TicketCommentRead]:
        ticket = self.get_ticket(ticket_id, actor)
        comments = self.tickets.list_comments(
            ticket.id,
            include_internal=actor.role == UserRole.ADMIN,
        )
        return [TicketCommentRead.model_validate(comment) for comment in comments]

    def list_history(self, ticket_id: UUID, actor: User) -> list[TicketHistoryRead]:
        self._require_admin(actor)
        ticket = self.get_ticket(ticket_id, actor)
        return [
            TicketHistoryRead.model_validate(item) for item in self.tickets.list_history(ticket.id)
        ]

    def statistics(self, filters: TicketFilters, actor: User) -> TicketStatistics:
        filters = self._scope_filters(filters, actor)
        return TicketStatistics.model_validate(self.tickets.statistics(filters))

    def _scope_filters(self, filters: TicketFilters, actor: User) -> TicketFilters:
        if actor.role == UserRole.ADMIN:
            return filters
        return TicketFilters(**{**filters.__dict__, "created_by_id": actor.id})

    def _require_ticket_access(self, ticket: Ticket, actor: User) -> None:
        if actor.role != UserRole.ADMIN and ticket.created_by_id != actor.id:
            raise TicketAccessDeniedError()

    def _require_admin(self, actor: User) -> None:
        if actor.role != UserRole.ADMIN:
            raise AuthorizationError("Only admins may perform this ticket action")

    def _require_not_closed(self, ticket: Ticket) -> None:
        if ticket.status == TicketStatus.CLOSED:
            raise TicketClosedError()

    def _change_priority(self, ticket: Ticket, priority: TicketPriority, actor: User) -> None:
        self._add_history(
            ticket,
            actor,
            TicketHistoryEvent.PRIORITY_CHANGED,
            ticket.priority.value,
            priority.value,
        )
        ticket.priority = priority

    def _change_category(self, ticket: Ticket, category: TicketCategory, actor: User) -> None:
        self._add_history(
            ticket,
            actor,
            TicketHistoryEvent.TICKET_UPDATED,
            ticket.category.value,
            category.value,
        )
        ticket.category = category

    def _add_history(
        self,
        ticket: Ticket,
        actor: User,
        event_type: TicketHistoryEvent,
        old_value: str | None,
        new_value: str | None,
    ) -> None:
        self.tickets.save(
            TicketHistory(
                ticket=ticket,
                changed_by_id=actor.id,
                event_type=event_type,
                old_value=old_value,
                new_value=new_value,
            )
        )

    def _apply_status_timestamps(
        self,
        ticket: Ticket,
        old_status: TicketStatus,
        new_status: TicketStatus,
    ) -> None:
        now = datetime.now(UTC)
        if new_status == TicketStatus.RESOLVED:
            ticket.resolved_at = now
        if old_status == TicketStatus.RESOLVED and new_status == TicketStatus.OPEN:
            ticket.resolved_at = None
        if new_status == TicketStatus.CLOSED:
            ticket.closed_at = now
        if old_status == TicketStatus.CLOSED and new_status == TicketStatus.OPEN:
            ticket.closed_at = None
