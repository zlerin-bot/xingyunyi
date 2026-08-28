from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable

MIN_HANDLE_LENGTH = 1
MAX_HANDLE_LENGTH = 32
HANDLE_PATTERN = re.compile(r"^[^\W_]+(?:-[^\W_]+)*$", flags=re.UNICODE)
RESERVED_HANDLES = frozenset(
    {
        "admin",
        "agentpost",
        "api",
        "app",
        "connect",
        "directory",
        "help",
        "inbox",
        "login",
        "logout",
        "mcp",
        "orbit",
        "root",
        "security",
        "settings",
        "signup",
        "support",
        "system",
        "www",
    }
)


def canonicalize_agent_handle(value: str) -> str:
    canonical = unicodedata.normalize("NFKC", value.strip()).casefold()
    if not MIN_HANDLE_LENGTH <= len(canonical) <= MAX_HANDLE_LENGTH:
        raise ValueError(
            f"handle must contain between {MIN_HANDLE_LENGTH} and {MAX_HANDLE_LENGTH} characters"
        )
    if not HANDLE_PATTERN.fullmatch(canonical):
        raise ValueError("handle must contain only letters, digits, and single internal hyphens")
    if canonical in RESERVED_HANDLES:
        raise ValueError("handle is reserved by AgentPost")
    return canonical


def available_handle_suggestions(
    handle: str,
    *,
    is_available: Callable[[str], bool],
    limit: int = 3,
) -> list[str]:
    """Return short deterministic alternatives; never add opaque random material."""

    canonical = canonicalize_agent_handle(handle)
    candidates = [f"{canonical}-agent", *(f"{canonical}-{number}" for number in range(2, 20))]
    suggestions: list[str] = []
    for candidate in candidates:
        if len(candidate) <= MAX_HANDLE_LENGTH and is_available(candidate):
            suggestions.append(candidate)
            if len(suggestions) == limit:
                break
    return suggestions
