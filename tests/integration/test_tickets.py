from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.user import User, UserRole
from tests.conftest import auth_header

API_PREFIX = get_settings().api_v1_prefix
PASSWORD = "StrongPassword123"


def create_user(db_session: Session, email: str, role: UserRole = UserRole.USER) -> User:
    user = User(
        email=email,
        full_name=email.split("@")[0].title(),
        hashed_password=hash_password(PASSWORD),
        role=role,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def create_ticket(
    client: TestClient,
    headers: dict[str, str],
    title: str = "Login failure",
    priority: str = "MEDIUM",
    category: str = "TECHNICAL",
) -> dict[str, Any]:
    response = client.post(
        f"{API_PREFIX}/tickets",
        json={
            "title": title,
            "description": f"Detailed report for {title}",
            "priority": priority,
            "category": category,
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def test_ticket_creation_records_defaults_and_history(
    client: TestClient,
    normal_user: User,
) -> None:
    headers = auth_header(client, normal_user.email, PASSWORD)

    ticket = create_ticket(client, headers)

    assert ticket["status"] == "OPEN"
    assert ticket["created_by_id"] == str(normal_user.id)
    history = client.get(f"{API_PREFIX}/tickets/{ticket['id']}/history", headers=headers)
    assert history.status_code == 403


def test_ticket_access_control_scopes_normal_users(
    client: TestClient,
    db_session: Session,
    normal_user: User,
) -> None:
    other_user = create_user(db_session, "other@example.com")
    user_headers = auth_header(client, normal_user.email, PASSWORD)
    other_headers = auth_header(client, other_user.email, PASSWORD)
    own_ticket = create_ticket(client, user_headers, title="Own ticket")
    create_ticket(client, other_headers, title="Other ticket")

    listing = client.get(f"{API_PREFIX}/tickets", headers=user_headers)
    forbidden = client.get(f"{API_PREFIX}/tickets/{own_ticket['id']}", headers=other_headers)

    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["title"] == "Own ticket"
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "TICKET_ACCESS_DENIED"


def test_admin_can_filter_paginate_and_search_tickets(
    client: TestClient,
    admin_user: User,
    normal_user: User,
) -> None:
    user_headers = auth_header(client, normal_user.email, PASSWORD)
    admin_headers = auth_header(client, admin_user.email, PASSWORD)
    create_ticket(client, user_headers, title="Billing portal blank", category="BILLING")
    create_ticket(client, user_headers, title="Webhook retries", category="FEATURE_REQUEST")
    create_ticket(client, user_headers, title="Billing export failure", category="BILLING")

    response = client.get(
        f"{API_PREFIX}/tickets",
        params={"category": "BILLING", "q": "Billing", "page": 1, "page_size": 1},
        headers=admin_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["page_size"] == 1
    assert body["total_pages"] == 2
    assert "Billing" in body["items"][0]["title"]


def test_user_and_admin_update_rules(
    client: TestClient,
    admin_user: User,
    normal_user: User,
) -> None:
    user_headers = auth_header(client, normal_user.email, PASSWORD)
    admin_headers = auth_header(client, admin_user.email, PASSWORD)
    ticket = create_ticket(client, user_headers)

    user_update = client.patch(
        f"{API_PREFIX}/tickets/{ticket['id']}",
        json={"title": "Updated by customer"},
        headers=user_headers,
    )
    user_priority = client.patch(
        f"{API_PREFIX}/tickets/{ticket['id']}/priority",
        json={"priority": "URGENT"},
        headers=user_headers,
    )
    admin_update = client.patch(
        f"{API_PREFIX}/tickets/{ticket['id']}",
        json={"category": "ACCOUNT", "priority": "HIGH"},
        headers=admin_headers,
    )

    assert user_update.status_code == 200
    assert user_update.json()["title"] == "Updated by customer"
    assert user_priority.status_code == 403
    assert admin_update.status_code == 200
    assert admin_update.json()["category"] == "ACCOUNT"
    assert admin_update.json()["priority"] == "HIGH"


def test_status_workflow_and_reopen_timestamps(
    client: TestClient,
    admin_user: User,
    normal_user: User,
) -> None:
    user_headers = auth_header(client, normal_user.email, PASSWORD)
    admin_headers = auth_header(client, admin_user.email, PASSWORD)
    ticket = create_ticket(client, user_headers)

    invalid = client.patch(
        f"{API_PREFIX}/tickets/{ticket['id']}/status",
        json={"status": "CLOSED"},
        headers=admin_headers,
    )
    resolved = client.patch(
        f"{API_PREFIX}/tickets/{ticket['id']}/status",
        json={"status": "RESOLVED"},
        headers=admin_headers,
    )
    reopened = client.patch(
        f"{API_PREFIX}/tickets/{ticket['id']}/status",
        json={"status": "OPEN"},
        headers=user_headers,
    )

    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "INVALID_STATUS_TRANSITION"
    assert resolved.status_code == 200
    assert resolved.json()["resolved_at"] is not None
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "OPEN"
    assert reopened.json()["resolved_at"] is None


def test_assignment_validation_requires_active_admins(
    client: TestClient,
    admin_user: User,
    normal_user: User,
) -> None:
    user_headers = auth_header(client, normal_user.email, PASSWORD)
    admin_headers = auth_header(client, admin_user.email, PASSWORD)
    ticket = create_ticket(client, user_headers)

    invalid = client.patch(
        f"{API_PREFIX}/tickets/{ticket['id']}/assignee",
        json={"assigned_to_id": str(normal_user.id)},
        headers=admin_headers,
    )
    valid = client.patch(
        f"{API_PREFIX}/tickets/{ticket['id']}/assignee",
        json={"assigned_to_id": str(admin_user.id)},
        headers=admin_headers,
    )

    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "INVALID_ASSIGNEE"
    assert valid.status_code == 200
    assert valid.json()["assigned_to_id"] == str(admin_user.id)


def test_comments_internal_visibility_and_history(
    client: TestClient,
    admin_user: User,
    normal_user: User,
) -> None:
    user_headers = auth_header(client, normal_user.email, PASSWORD)
    admin_headers = auth_header(client, admin_user.email, PASSWORD)
    ticket = create_ticket(client, user_headers)

    public_comment = client.post(
        f"{API_PREFIX}/tickets/{ticket['id']}/comments",
        json={"content": "Public customer note"},
        headers=user_headers,
    )
    forbidden_internal = client.post(
        f"{API_PREFIX}/tickets/{ticket['id']}/comments",
        json={"content": "Hidden note", "is_internal": True},
        headers=user_headers,
    )
    internal_comment = client.post(
        f"{API_PREFIX}/tickets/{ticket['id']}/comments",
        json={"content": "Admin-only triage note", "is_internal": True},
        headers=admin_headers,
    )
    user_comments = client.get(
        f"{API_PREFIX}/tickets/{ticket['id']}/comments",
        headers=user_headers,
    )
    admin_comments = client.get(
        f"{API_PREFIX}/tickets/{ticket['id']}/comments",
        headers=admin_headers,
    )
    history = client.get(f"{API_PREFIX}/tickets/{ticket['id']}/history", headers=admin_headers)

    assert public_comment.status_code == 201
    assert forbidden_internal.status_code == 403
    assert forbidden_internal.json()["error"]["code"] == "INTERNAL_COMMENT_FORBIDDEN"
    assert internal_comment.status_code == 201
    assert len(user_comments.json()) == 1
    assert len(admin_comments.json()) == 2
    assert history.status_code == 200
    assert "COMMENT_ADDED" in {item["event_type"] for item in history.json()}


def test_statistics_are_scoped_for_users_and_global_for_admins(
    client: TestClient,
    db_session: Session,
    admin_user: User,
    normal_user: User,
) -> None:
    other_user = create_user(db_session, "stats-other@example.com")
    user_headers = auth_header(client, normal_user.email, PASSWORD)
    other_headers = auth_header(client, other_user.email, PASSWORD)
    admin_headers = auth_header(client, admin_user.email, PASSWORD)
    create_ticket(client, user_headers, priority="HIGH", category="ACCOUNT")
    create_ticket(client, other_headers, priority="LOW", category="BILLING")

    user_stats = client.get(f"{API_PREFIX}/tickets/statistics", headers=user_headers)
    admin_stats = client.get(f"{API_PREFIX}/tickets/statistics", headers=admin_headers)

    assert user_stats.status_code == 200
    assert user_stats.json()["total"] == 1
    assert user_stats.json()["by_priority"]["HIGH"] == 1
    assert admin_stats.status_code == 200
    assert admin_stats.json()["total"] == 2
