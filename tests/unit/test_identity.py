from __future__ import annotations

import base64

import pytest
from pydantic import SecretStr

from agentpost.identity.addressing import (
    address_domain,
    address_local_id,
    canonicalize_agent_address,
)
from agentpost.identity.api_keys import API_KEY_MARKER, digest_api_key, generate_api_key


def test_address_is_canonical_ascii_lowercase() -> None:
    address = canonicalize_agent_address("  Alice.Research@Agents.Example.COM  ")

    assert address == "alice.research@agents.example.com"
    assert address_local_id(address) == "alice.research"
    assert address_domain(address) == "agents.example.com"


@pytest.mark.parametrize(
    "address",
    [
        "alice",
        "@agents.local",
        "alice@",
        "alice..research@agents.local",
        "álîce@agents.local",
        "alice@agents..local",
        "alice@-agents.local",
    ],
)
def test_invalid_agent_addresses_are_rejected(address: str) -> None:
    with pytest.raises(ValueError):
        canonicalize_agent_address(address)


def test_generated_api_key_contains_at_least_256_bits_of_entropy() -> None:
    api_key = generate_api_key()
    encoded_random_part = api_key.removeprefix(API_KEY_MARKER)
    padding = "=" * (-len(encoded_random_part) % 4)

    assert api_key.startswith(API_KEY_MARKER)
    assert len(base64.urlsafe_b64decode(encoded_random_part + padding)) == 32


def test_api_key_digest_is_hmac_sha256_and_pepper_bound() -> None:
    api_key = "agt_test-key-material"
    first = digest_api_key(api_key, SecretStr("pepper-one"))
    second = digest_api_key(api_key, SecretStr("pepper-two"))

    assert len(first) == 64
    assert first != api_key
    assert first != second
