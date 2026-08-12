from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from agentpost.db import Database
from agentpost.messaging.models import AuditLog, Delivery, IdempotencyRecord, Message


def register(client: TestClient, address: str) -> dict[str, Any]:
    response = client.post(
        "/api/v1/agents",
        json={
            "address": address,
            "display_name": address.partition("@")[0].title(),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def bearer(registration: dict[str, Any], **extra: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {registration['api_key']}", **extra}


def policy_url(registration: dict[str, Any]) -> str:
    return f"/api/v1/agents/{registration['agent']['id']}/access-policy"


def rules_url(registration: dict[str, Any]) -> str:
    return f"/api/v1/agents/{registration['agent']['id']}/access-rules"


def get_policy(
    client: TestClient,
    owner: dict[str, Any],
    *,
    actor: dict[str, Any] | None = None,
):
    return client.get(policy_url(owner), headers=bearer(actor or owner))


def set_policy(
    client: TestClient,
    owner: dict[str, Any],
    inbound_policy: str,
    *,
    actor: dict[str, Any] | None = None,
    **headers: str,
):
    return client.put(
        policy_url(owner),
        headers=bearer(actor or owner, **headers),
        json={"inbound_policy": inbound_policy},
    )


def create_rule(
    client: TestClient,
    owner: dict[str, Any],
    *,
    effect: str,
    subject_type: str,
    subject: str,
    actor: dict[str, Any] | None = None,
    **headers: str,
):
    return client.post(
        rules_url(owner),
        headers=bearer(actor or owner, **headers),
        json={
            "effect": effect,
            "subject_type": subject_type,
            "subject": subject,
        },
    )


def message_payload(recipient: dict[str, Any], body: str = "Hello") -> dict[str, Any]:
    return {
        "to": [{"address": recipient["agent"]["address"]}],
        "type": "message",
        "subject": "ACL acceptance",
        "content": {"format": "text", "body": body},
        "attachments": [],
        "priority": "normal",
        "requires_ack": True,
        "metadata": {},
        "expires_at": None,
    }


def send_message(
    client: TestClient,
    sender: dict[str, Any],
    recipient: dict[str, Any],
    *,
    key: str,
    body: str = "Hello",
):
    return client.post(
        "/api/v1/messages",
        headers=bearer(sender, **{"Idempotency-Key": key}),
        json=message_payload(recipient, body),
    )


def reply_message(
    client: TestClient,
    sender: dict[str, Any],
    parent_message_id: str,
    *,
    key: str,
):
    return client.post(
        f"/api/v1/messages/{parent_message_id}/reply",
        headers=bearer(sender, **{"Idempotency-Key": key}),
        json={
            "type": "message",
            "subject": "ACL reply",
            "content": {"format": "text", "body": "Reply"},
            "attachments": [],
            "priority": "normal",
            "requires_ack": True,
            "metadata": {},
            "expires_at": None,
        },
    )


def error_code(response: Any) -> str:
    assert "error" in response.json(), response.text
    return str(response.json()["error"]["code"])


def transport_counts(database: Database) -> tuple[int, int, int]:
    with database.session_factory() as session:
        return (
            int(session.scalar(select(func.count()).select_from(Message)) or 0),
            int(session.scalar(select(func.count()).select_from(Delivery)) or 0),
            int(session.scalar(select(func.count()).select_from(IdempotencyRecord)) or 0),
        )


def audit_rows(database: Database) -> list[AuditLog]:
    with database.session_factory() as session:
        return list(session.scalars(select(AuditLog).order_by(AuditLog.created_at, AuditLog.id)))


def assert_delivery_denied(response: Any) -> None:
    assert response.status_code == 403, response.text
    assert error_code(response) == "DELIVERY_NOT_ALLOWED"


def test_default_policy_is_public_and_policy_resources_are_owner_only(
    client: TestClient,
) -> None:
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")

    response = get_policy(client, alice)
    assert response.status_code == 200, response.text
    assert response.json() == {
        "agent_id": alice["agent"]["id"],
        "inbound_policy": "public",
        "rules": [],
    }

    assert client.get(policy_url(alice)).status_code == 401
    assert get_policy(client, alice, actor=bob).status_code == 404
    assert set_policy(client, alice, "private", actor=bob).status_code == 404
    hidden_create = create_rule(
        client,
        alice,
        effect="allow",
        subject_type="agent",
        subject=bob["agent"]["address"],
        actor=bob,
    )
    assert hidden_create.status_code == 404

    accepted = send_message(client, alice, bob, key="default-public")
    assert accepted.status_code == 201, accepted.text


@pytest.mark.parametrize(
    ("method", "payload"),
    [
        ("put", {"inbound_policy": "public", "unexpected": True}),
        ("put", {"inbound_policy": "everyone"}),
        (
            "post",
            {
                "effect": "allow",
                "subject_type": "agent",
                "subject": "alice@agents.local",
                "unexpected": True,
            },
        ),
        (
            "post",
            {
                "effect": "permit",
                "subject_type": "agent",
                "subject": "alice@agents.local",
            },
        ),
        (
            "post",
            {
                "effect": "allow",
                "subject_type": "organization",
                "subject": "agents.local",
            },
        ),
        (
            "post",
            {"effect": "allow", "subject_type": "agent", "subject": "not-an-address"},
        ),
        (
            "post",
            {"effect": "block", "subject_type": "domain", "subject": "bad/domain"},
        ),
    ],
)
def test_policy_and_rule_payloads_are_strict(
    client: TestClient,
    method: str,
    payload: dict[str, Any],
) -> None:
    bob = register(client, f"bob-{method}-{abs(hash(str(payload))) % 1_000_000}@agents.local")
    url = policy_url(bob) if method == "put" else rules_url(bob)

    response = client.request(method, url, headers=bearer(bob), json=payload)

    assert response.status_code == 422, response.text
    assert error_code(response) == "SCHEMA_VALIDATION_FAILED"
    current = get_policy(client, bob)
    assert current.status_code == 200
    assert current.json()["inbound_policy"] == "public"
    assert current.json()["rules"] == []


def test_rules_are_canonical_unique_owner_scoped_and_deletable(client: TestClient) -> None:
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")

    agent_rule = create_rule(
        client,
        bob,
        effect="allow",
        subject_type="agent",
        subject="  ALICE@AGENTS.LOCAL  ",
    )
    domain_rule = create_rule(
        client,
        bob,
        effect="block",
        subject_type="domain",
        subject="  PARTNER.EXAMPLE  ",
    )
    assert agent_rule.status_code == 201, agent_rule.text
    assert domain_rule.status_code == 201, domain_rule.text
    assert agent_rule.json()["subject"] == "alice@agents.local"
    assert domain_rule.json()["subject"] == "partner.example"
    assert agent_rule.json()["agent_id"] == bob["agent"]["id"]

    duplicate = create_rule(
        client,
        bob,
        effect="allow",
        subject_type="agent",
        subject=alice["agent"]["address"],
    )
    assert duplicate.status_code == 409, duplicate.text
    assert error_code(duplicate) == "ACCESS_RULE_ALREADY_EXISTS"

    policy = get_policy(client, bob)
    assert policy.status_code == 200
    returned_rules = {
        (item["effect"], item["subject_type"], item["subject"]) for item in policy.json()["rules"]
    }
    assert returned_rules == {
        ("allow", "agent", "alice@agents.local"),
        ("block", "domain", "partner.example"),
    }

    rule_id = agent_rule.json()["id"]
    hidden_delete = client.delete(
        f"{rules_url(bob)}/{rule_id}",
        headers=bearer(alice),
    )
    assert hidden_delete.status_code == 404
    deleted = client.delete(f"{rules_url(bob)}/{rule_id}", headers=bearer(bob))
    assert deleted.status_code == 204, deleted.text
    assert not deleted.content
    missing = client.delete(f"{rules_url(bob)}/{rule_id}", headers=bearer(bob))
    assert missing.status_code == 404


def test_agent_block_denies_only_the_matching_sender(client: TestClient) -> None:
    alice = register(client, "alice@agents.local")
    eve = register(client, "eve@agents.local")
    bob = register(client, "bob@agents.local")
    blocked = create_rule(
        client,
        bob,
        effect="block",
        subject_type="agent",
        subject=alice["agent"]["address"],
    )
    assert blocked.status_code == 201, blocked.text

    assert_delivery_denied(send_message(client, alice, bob, key="agent-blocked"))
    accepted = send_message(client, eve, bob, key="agent-not-blocked")
    assert accepted.status_code == 201, accepted.text


def test_domain_block_and_block_precedence_over_allow(client: TestClient) -> None:
    alice = register(client, "alice@partner.example")
    eve = register(client, "eve@trusted.example")
    bob = register(client, "bob@agents.local")
    assert (
        create_rule(
            client,
            bob,
            effect="allow",
            subject_type="agent",
            subject=alice["agent"]["address"],
        ).status_code
        == 201
    )
    assert (
        create_rule(
            client,
            bob,
            effect="block",
            subject_type="domain",
            subject="PARTNER.EXAMPLE",
        ).status_code
        == 201
    )

    assert_delivery_denied(send_message(client, alice, bob, key="domain-blocked"))
    accepted = send_message(client, eve, bob, key="domain-not-blocked")
    assert accepted.status_code == 201, accepted.text


def test_allowlist_accepts_agent_or_domain_and_rejects_everyone_else(
    client: TestClient,
) -> None:
    alice = register(client, "alice@outside.example")
    trusted = register(client, "worker@trusted.example")
    eve = register(client, "eve@outside.example")
    bob = register(client, "bob@agents.local")
    assert set_policy(client, bob, "allowlist").status_code == 200
    assert (
        create_rule(
            client,
            bob,
            effect="allow",
            subject_type="agent",
            subject=alice["agent"]["address"],
        ).status_code
        == 201
    )
    assert (
        create_rule(
            client,
            bob,
            effect="allow",
            subject_type="domain",
            subject="trusted.example",
        ).status_code
        == 201
    )

    assert send_message(client, alice, bob, key="allow-agent").status_code == 201
    assert send_message(client, trusted, bob, key="allow-domain").status_code == 201
    assert_delivery_denied(send_message(client, eve, bob, key="allow-deny-eve"))

    assert (
        create_rule(
            client,
            bob,
            effect="block",
            subject_type="agent",
            subject=trusted["agent"]["address"],
        ).status_code
        == 201
    )
    assert_delivery_denied(send_message(client, trusted, bob, key="block-wins"))


def test_contacts_only_uses_existing_correspondence_as_the_mvp_contact_model(
    client: TestClient,
) -> None:
    alice = register(client, "alice@agents.local")
    eve = register(client, "eve@agents.local")
    bob = register(client, "bob@agents.local")
    first = send_message(client, alice, bob, key="establish-contact")
    assert first.status_code == 201, first.text
    updated = set_policy(client, bob, "contacts_only")
    assert updated.status_code == 200, updated.text

    existing_contact = send_message(client, alice, bob, key="existing-contact")
    assert existing_contact.status_code == 201, existing_contact.text
    assert_delivery_denied(send_message(client, eve, bob, key="not-a-contact"))


def test_private_policy_allows_only_self_delivery(client: TestClient) -> None:
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")
    assert set_policy(client, bob, "private").status_code == 200
    assert (
        create_rule(
            client,
            bob,
            effect="allow",
            subject_type="agent",
            subject=alice["agent"]["address"],
        ).status_code
        == 201
    )

    assert_delivery_denied(send_message(client, alice, bob, key="private-denied"))
    self_delivery = send_message(client, bob, bob, key="private-self")
    assert self_delivery.status_code == 201, self_delivery.text


def test_policy_changes_do_not_revoke_old_mail_but_new_reply_is_rechecked(
    client: TestClient,
    database: Database,
) -> None:
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")
    original = send_message(client, alice, bob, key="old-mail")
    assert original.status_code == 201, original.text
    original_id = original.json()["message_id"]

    assert (
        create_rule(
            client,
            bob,
            effect="block",
            subject_type="agent",
            subject=alice["agent"]["address"],
        ).status_code
        == 201
    )
    old_mail = client.get(f"/api/v1/messages/{original_id}", headers=bearer(bob))
    assert old_mail.status_code == 200, old_mail.text

    assert (
        create_rule(
            client,
            alice,
            effect="block",
            subject_type="agent",
            subject=bob["agent"]["address"],
        ).status_code
        == 201
    )
    before = transport_counts(database)
    denied_reply = reply_message(client, bob, original_id, key="new-reply-denied")
    assert_delivery_denied(denied_reply)
    assert transport_counts(database) == before


def test_rejected_delivery_creates_no_transport_records_but_is_audited(
    client: TestClient,
    database: Database,
) -> None:
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")
    assert set_policy(client, bob, "allowlist").status_code == 200
    before_counts = transport_counts(database)
    before_audits = len(audit_rows(database))

    response = send_message(client, alice, bob, key="rejected-zero-state")

    assert_delivery_denied(response)
    assert transport_counts(database) == before_counts
    rows = audit_rows(database)
    assert len(rows) == before_audits + 1
    rejection = rows[-1]
    assert str(rejection.actor_agent_id) == alice["agent"]["id"]
    assert rejection.outcome in {"denied", "failure"}
    assert (rejection.reason_code or "").casefold() in {
        "explicit_block",
        "private_policy",
        "allow_rule_required",
    }
    assert rejection.audit_metadata.get("recipient_agent_id") == bob["agent"]["id"]


def test_an_accepted_idempotent_request_replays_after_sender_is_blocked(
    client: TestClient,
    database: Database,
) -> None:
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")
    first = send_message(
        client,
        alice,
        bob,
        key="accepted-before-block",
        body="Same request",
    )
    assert first.status_code == 201, first.text
    first_id = first.json()["message_id"]
    assert (
        create_rule(
            client,
            bob,
            effect="block",
            subject_type="agent",
            subject=alice["agent"]["address"],
        ).status_code
        == 201
    )

    replay = send_message(
        client,
        alice,
        bob,
        key="accepted-before-block",
        body="Same request",
    )
    assert replay.status_code == 200, replay.text
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert replay.json()["message_id"] == first_id
    assert transport_counts(database) == (1, 1, 1)
    assert_delivery_denied(
        send_message(client, alice, bob, key="new-after-block", body="New request")
    )
    assert transport_counts(database) == (1, 1, 1)


def test_policy_and_rule_mutations_have_request_correlated_audit_rows(
    client: TestClient,
    database: Database,
) -> None:
    alice = register(client, "alice@agents.local")
    bob = register(client, "bob@agents.local")
    updated = set_policy(
        client,
        bob,
        "allowlist",
        **{"X-Request-ID": "acl-policy-request"},
    )
    assert updated.status_code == 200, updated.text
    created = create_rule(
        client,
        bob,
        effect="allow",
        subject_type="agent",
        subject=alice["agent"]["address"],
        **{"X-Request-ID": "acl-rule-create-request"},
    )
    assert created.status_code == 201, created.text
    deleted = client.delete(
        f"{rules_url(bob)}/{created.json()['id']}",
        headers=bearer(bob, **{"X-Request-ID": "acl-rule-delete-request"}),
    )
    assert deleted.status_code == 204, deleted.text

    rows = audit_rows(database)
    by_request_id = {row.request_id: row for row in rows}
    assert by_request_id["acl-policy-request"].action == "access.policy_updated"
    assert by_request_id["acl-rule-create-request"].action == "access.rule_created"
    assert by_request_id["acl-rule-delete-request"].action == "access.rule_deleted"
    for request_id in (
        "acl-policy-request",
        "acl-rule-create-request",
        "acl-rule-delete-request",
    ):
        row = by_request_id[request_id]
        assert str(row.actor_agent_id) == bob["agent"]["id"]
        assert row.outcome == "success"
