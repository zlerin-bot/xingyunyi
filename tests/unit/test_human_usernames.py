import pytest

from agentpost.accounts.usernames import (
    HumanUsernameAlreadyRegisteredError,
    available_human_username,
    canonicalize_human_username,
)
from agentpost.control.models import HumanUser
from agentpost.db import Database


@pytest.mark.parametrize("value", ["020", "mars-113", "alice"])
def test_human_username_accepts_user_facing_identifiers(value: str) -> None:
    assert canonicalize_human_username(value.upper()) == value


@pytest.mark.parametrize("value", ["02", "-020", "020-", "human--name", "张三"])
def test_human_username_rejects_ambiguous_or_unstable_forms(value: str) -> None:
    with pytest.raises(ValueError):
        canonicalize_human_username(value)


def test_requested_human_username_is_globally_unique(database: Database) -> None:
    with database.session_factory() as session:
        session.add(
            HumanUser(
                email="first@example.com",
                username="020",
                display_name="First",
                status="active",
            )
        )
        session.flush()

        with pytest.raises(HumanUsernameAlreadyRegisteredError):
            available_human_username(
                session,
                requested="020",
                email="second@example.com",
            )
