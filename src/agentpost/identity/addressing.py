from __future__ import annotations

import re

_ADDRESS_PATTERN = re.compile(
    r"^(?P<local>[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?)@"
    r"(?P<domain>[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*)$",
    flags=re.ASCII,
)


def canonicalize_agent_address(value: str) -> str:
    """Return the stable ASCII, lowercase representation of an agent address."""

    if not isinstance(value, str):
        raise ValueError("agent address must be a string")
    try:
        value.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError("agent address must contain ASCII characters only") from exc

    canonical = value.strip().lower()
    if len(canonical) > 320 or not _ADDRESS_PATTERN.fullmatch(canonical):
        raise ValueError("agent address must be a valid local_agent_id@domain address")
    if ".." in canonical:
        raise ValueError("agent address must not contain consecutive dots")
    return canonical


def address_domain(address: str) -> str:
    """Extract the already-canonical domain component."""

    return canonicalize_agent_address(address).partition("@")[2]


def address_local_id(address: str) -> str:
    """Extract the already-canonical local identity component."""

    return canonicalize_agent_address(address).partition("@")[0]
