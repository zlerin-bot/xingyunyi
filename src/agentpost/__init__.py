"""AgentPost asynchronous agent messaging infrastructure."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agentpost_sdk import AgentPost

__all__ = ["AgentPost", "__version__"]

__version__ = "0.1.22"


def __getattr__(name: str) -> Any:
    """Load the HTTP SDK facade only when callers explicitly request it."""
    if name == "AgentPost":
        from agentpost_sdk import AgentPost

        return AgentPost
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
