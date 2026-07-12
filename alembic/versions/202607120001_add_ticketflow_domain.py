"""add ticketflow domain

Revision ID: 202607120001
Revises: 202607110002
Create Date: 2026-07-12 23:55:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.database.base import GUID

revision: str = "202607120001"
down_revision: str | None = "202607110002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tickets",
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "OPEN",
                "IN_PROGRESS",
                "WAITING_FOR_CUSTOMER",
                "RESOLVED",
                "CLOSED",
                name="ticketstatus",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.Enum("LOW", "MEDIUM", "HIGH", "URGENT", name="ticketpriority", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "category",
            sa.Enum(
                "TECHNICAL",
                "BILLING",
                "ACCOUNT",
                "FEATURE_REQUEST",
                "OTHER",
                name="ticketcategory",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("created_by_id", GUID(), nullable=False),
        sa.Column("assigned_to_id", GUID(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", GUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["assigned_to_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tickets_assigned_to_id", "tickets", ["assigned_to_id"], unique=False)
    op.create_index("ix_tickets_category", "tickets", ["category"], unique=False)
    op.create_index("ix_tickets_created_at", "tickets", ["created_at"], unique=False)
    op.create_index("ix_tickets_created_by_id", "tickets", ["created_by_id"], unique=False)
    op.create_index("ix_tickets_id", "tickets", ["id"], unique=False)
    op.create_index("ix_tickets_priority", "tickets", ["priority"], unique=False)
    op.create_index("ix_tickets_status", "tickets", ["status"], unique=False)

    op.create_table(
        "ticket_comments",
        sa.Column("ticket_id", GUID(), nullable=False),
        sa.Column("author_id", GUID(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_internal", sa.Boolean(), nullable=False),
        sa.Column("id", GUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ticket_comments_author_id", "ticket_comments", ["author_id"], unique=False)
    op.create_index("ix_ticket_comments_id", "ticket_comments", ["id"], unique=False)
    op.create_index("ix_ticket_comments_ticket_id", "ticket_comments", ["ticket_id"], unique=False)

    op.create_table(
        "ticket_history",
        sa.Column("ticket_id", GUID(), nullable=False),
        sa.Column("changed_by_id", GUID(), nullable=False),
        sa.Column(
            "event_type",
            sa.Enum(
                "TICKET_CREATED",
                "STATUS_CHANGED",
                "PRIORITY_CHANGED",
                "ASSIGNEE_CHANGED",
                "COMMENT_ADDED",
                "TICKET_UPDATED",
                name="tickethistoryevent",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("id", GUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["changed_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ticket_history_changed_by_id",
        "ticket_history",
        ["changed_by_id"],
        unique=False,
    )
    op.create_index("ix_ticket_history_id", "ticket_history", ["id"], unique=False)
    op.create_index("ix_ticket_history_ticket_id", "ticket_history", ["ticket_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ticket_history_ticket_id", table_name="ticket_history")
    op.drop_index("ix_ticket_history_id", table_name="ticket_history")
    op.drop_index("ix_ticket_history_changed_by_id", table_name="ticket_history")
    op.drop_table("ticket_history")
    op.drop_index("ix_ticket_comments_ticket_id", table_name="ticket_comments")
    op.drop_index("ix_ticket_comments_id", table_name="ticket_comments")
    op.drop_index("ix_ticket_comments_author_id", table_name="ticket_comments")
    op.drop_table("ticket_comments")
    op.drop_index("ix_tickets_status", table_name="tickets")
    op.drop_index("ix_tickets_priority", table_name="tickets")
    op.drop_index("ix_tickets_id", table_name="tickets")
    op.drop_index("ix_tickets_created_by_id", table_name="tickets")
    op.drop_index("ix_tickets_created_at", table_name="tickets")
    op.drop_index("ix_tickets_category", table_name="tickets")
    op.drop_index("ix_tickets_assigned_to_id", table_name="tickets")
    op.drop_table("tickets")
