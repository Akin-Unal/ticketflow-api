from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.database.session import SessionLocal
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
from app.repositories.user_repository import UserRepository

DEMO_PASSWORD = "StrongPassword123"


def get_or_create_user(
    db: Session,
    email: str,
    name: str,
    role: UserRole,
) -> User:
    users = UserRepository(db)
    user = users.get_by_email(email)
    if user:
        return user
    user = User(
        email=email,
        full_name=name,
        hashed_password=hash_password(DEMO_PASSWORD),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_ticket(
    db: Session,
    *,
    creator: User,
    title: str,
    description: str,
    priority: TicketPriority,
    category: TicketCategory,
    status: TicketStatus = TicketStatus.OPEN,
    assignee: User | None = None,
) -> Ticket:
    ticket = Ticket(
        title=title,
        description=description,
        priority=priority,
        category=category,
        status=status,
        created_by_id=creator.id,
        assigned_to_id=assignee.id if assignee else None,
    )
    db.add(ticket)
    db.flush()
    db.add(
        TicketHistory(
            ticket_id=ticket.id,
            changed_by_id=creator.id,
            event_type=TicketHistoryEvent.TICKET_CREATED,
            new_value=TicketStatus.OPEN.value,
        )
    )
    if status != TicketStatus.OPEN and assignee:
        db.add(
            TicketHistory(
                ticket_id=ticket.id,
                changed_by_id=assignee.id,
                event_type=TicketHistoryEvent.STATUS_CHANGED,
                old_value=TicketStatus.OPEN.value,
                new_value=status.value,
            )
        )
    return ticket


def seed_tickets(db: Session, admin: User, user_one: User, user_two: User) -> int:
    if db.query(Ticket).count() > 0:
        return 0

    tickets = [
        create_ticket(
            db,
            creator=user_one,
            title="Cannot sign in after password reset",
            description="The reset link worked, but the new password is rejected on login.",
            priority=TicketPriority.HIGH,
            category=TicketCategory.ACCOUNT,
            status=TicketStatus.IN_PROGRESS,
            assignee=admin,
        ),
        create_ticket(
            db,
            creator=user_one,
            title="Invoice PDF downloads as a blank file",
            description="The latest invoice opens, but all pages are empty.",
            priority=TicketPriority.MEDIUM,
            category=TicketCategory.BILLING,
        ),
        create_ticket(
            db,
            creator=user_two,
            title="Webhook retry setting request",
            description="We need configurable retry limits for failed webhook deliveries.",
            priority=TicketPriority.LOW,
            category=TicketCategory.FEATURE_REQUEST,
            status=TicketStatus.WAITING_FOR_CUSTOMER,
            assignee=admin,
        ),
        create_ticket(
            db,
            creator=user_two,
            title="API returns 500 for CSV export",
            description="Exports fail for date ranges longer than 90 days.",
            priority=TicketPriority.URGENT,
            category=TicketCategory.TECHNICAL,
            status=TicketStatus.RESOLVED,
            assignee=admin,
        ),
    ]
    db.flush()

    db.add_all(
        [
            TicketComment(
                ticket_id=tickets[0].id,
                author_id=user_one.id,
                content="This blocks our support team from logging in.",
            ),
            TicketComment(
                ticket_id=tickets[0].id,
                author_id=admin.id,
                content="Confirmed identity provider token mismatch.",
                is_internal=True,
            ),
            TicketComment(
                ticket_id=tickets[2].id,
                author_id=admin.id,
                content="Can you share the expected retry policy?",
            ),
            TicketComment(
                ticket_id=tickets[3].id,
                author_id=admin.id,
                content="Patch deployed and export verified.",
            ),
        ]
    )
    db.add(
        TicketHistory(
            ticket_id=tickets[0].id,
            changed_by_id=admin.id,
            event_type=TicketHistoryEvent.ASSIGNEE_CHANGED,
            old_value=None,
            new_value=str(admin.id),
        )
    )
    db.commit()
    return len(tickets)


def main() -> int:
    db = SessionLocal()
    try:
        admin = get_or_create_user(db, "admin@example.com", "Admin User", UserRole.ADMIN)
        user_one = get_or_create_user(db, "user@example.com", "Example User", UserRole.USER)
        user_two = get_or_create_user(db, "jane@example.com", "Jane Customer", UserRole.USER)
        ticket_count = seed_tickets(db, admin, user_one, user_two)
        print("Demo credentials:")
        print(f"  admin@example.com / {DEMO_PASSWORD}")
        print(f"  user@example.com / {DEMO_PASSWORD}")
        print(f"  jane@example.com / {DEMO_PASSWORD}")
        print(f"Tickets {'created' if ticket_count else 'already existed'}: {ticket_count}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
