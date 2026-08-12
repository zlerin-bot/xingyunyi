from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from agentpost.directory.schemas import DirectoryAgentProfile
from agentpost.directory.service import DirectoryFilters, InvalidDirectoryFilterError


def test_directory_filters_normalize_case_and_outer_whitespace() -> None:
    filters = DirectoryFilters.normalize(
        q="  BANK Desk  ",
        capability="  Financial-Research  ",
    )

    assert filters.q == "bank desk"
    assert filters.capability == "financial-research"


@pytest.mark.parametrize(
    ("q", "capability"),
    [
        (None, None),
        ("", None),
        ("   ", None),
        (None, ""),
        (None, "\u0000invalid"),
        ("line\nbreak", None),
        ("q" * 201, None),
        (None, "c" * 101),
    ],
)
def test_directory_filters_reject_unbounded_or_malformed_input(
    q: str | None,
    capability: str | None,
) -> None:
    with pytest.raises(InvalidDirectoryFilterError):
        DirectoryFilters.normalize(q=q, capability=capability)


def test_directory_profile_schema_forbids_internal_fields() -> None:
    now = datetime.now(UTC)
    public_profile = {
        "id": uuid4(),
        "address": "alice@agents.local",
        "display_name": "Alice",
        "description": None,
        "domain": "agents.local",
        "status": "active",
        "public_key": None,
        "capabilities": ["financial-research"],
        "endpoint": None,
        "created_at": now,
        "updated_at": now,
        "last_seen_at": None,
        "capability_verification": "self_declared",
        "owner_id": "must-not-leak",
    }

    with pytest.raises(ValidationError):
        DirectoryAgentProfile.model_validate(public_profile)
