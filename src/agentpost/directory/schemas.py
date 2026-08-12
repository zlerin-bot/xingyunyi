from __future__ import annotations

from typing import Literal

from agentpost.identity.schemas import AgentProfile, StrictModel


class DirectoryAgentProfile(AgentProfile):
    """A safe public profile returned as an unverified discovery candidate."""

    capability_verification: Literal["self_declared"] = "self_declared"


class DirectorySearchResponse(StrictModel):
    items: list[DirectoryAgentProfile]
