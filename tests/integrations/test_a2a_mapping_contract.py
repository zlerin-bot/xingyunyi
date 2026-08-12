from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MAPPING_PATH = ROOT / "docs" / "A2A_MAPPING.md"
CONTRACT_PATTERN = re.compile(
    r"<!-- BEGIN A2A_MAPPING_CONTRACT -->\s*```json\s*(\{.*?\})\s*```\s*"
    r"<!-- END A2A_MAPPING_CONTRACT -->",
    re.DOTALL,
)


def _mapping() -> str:
    return MAPPING_PATH.read_text(encoding="utf-8")


def _contract() -> dict[str, Any]:
    match = CONTRACT_PATTERN.search(_mapping())
    assert match is not None, "A2A mapping must expose its machine-checked contract registry"
    value = json.loads(match.group(1))
    assert isinstance(value, dict)
    return value


def _normalized_mapping() -> str:
    return " ".join(_mapping().replace("`", "").split()).casefold()


def test_a2a_and_delivery_keep_independent_state_machines() -> None:
    state = _contract()["state_ownership"]

    assert state == {
        "agentpost_delivery": ["accepted", "delivered", "read", "acked"],
        "a2a_task": [
            "submitted",
            "working",
            "input-required",
            "auth-required",
            "completed",
            "failed",
            "canceled",
            "rejected",
        ],
        "independent": True,
        "ack_task_effect": "none",
    }
    text = _normalized_mapping()
    assert "must remain two independent state machines" in text
    assert "agentpost ack must not map to a2a completed" in text
    assert "a message ack without a result leaves the task state unchanged" in text


def test_cross_protocol_binding_is_durable_and_retry_stable() -> None:
    binding = _contract()["binding"]

    assert binding == {
        "storage": "persistent",
        "survives_restart": True,
        "retry_reuses_binding": True,
    }
    text = _normalized_mapping()
    assert "an in-memory map is forbidden" in text
    assert "must survive process and server restart" in text
    assert "must resolve to the same agentpost message and the same a2a task" in text


def test_agent_card_has_a_legal_skill_fallback_and_truthful_capabilities() -> None:
    card = _contract()["agent_card"]

    assert card == {
        "skill_fallback": "agentpost-asynchronous-messaging",
        "streaming": False,
        "pushNotifications": False,
        "extendedAgentCard": False,
    }
    text = _normalized_mapping()
    assert "rather than inventing domain expertise" in text
    assert "must not advertise sse, websocket, webhook, push" in text
    assert "capabilities are self-declared discovery labels, not proof" in text


def test_thread_context_and_sender_authority_are_isolated() -> None:
    contract = _contract()

    assert contract["context_scope"] == [
        "local_agent",
        "authenticated_principal",
        "peer_endpoint",
    ]
    assert contract["sender_authority"] == "authenticated_principal"
    assert contract["metadata_from_is_authoritative"] is False
    text = _normalized_mapping()
    assert "correlation identifiers, not capabilities or authorization tokens" in text
    assert "must not merge their histories" in text
    assert "the authenticated principal is the only sender identity authority" in text
    assert "metadata.from" in text


def test_attachment_mapping_preserves_authorization_and_hides_storage() -> None:
    contract = _contract()

    assert contract["attachment_url"] == "authorized-https-or-short-lived-audience-bound-signed-url"
    text = _normalized_mapping()
    assert "must not contain storage_key, an object-store uri, or a local filesystem path" in text
    assert "authentication and per-object authorization" in text
    assert (
        "short-lived https signed url bound to the attachment, intended audience, and expiry"
        in text
    )
    assert "loopback/private/link-local destinations" in text


def test_a2a_never_replaces_the_persistent_inbox() -> None:
    contract = _contract()

    assert contract["persistent_inbox_retained"] is True
    text = _normalized_mapping()
    assert "the persistent agentpost inbox remains the source of truth" in text
    assert "must not replace the inbox abstraction" in text
    assert "if acceleration fails, accepted messages remain in the persistent inbox" in text
