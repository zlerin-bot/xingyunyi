"""Framework-agnostic synchronous Python client for AgentPost."""

from agentpost_sdk.client import AgentPost
from agentpost_sdk.errors import (
    AgentPostError,
    ApiError,
    AuthenticationError,
    AuthorizationError,
    ConfigurationError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ProtocolError,
    RateLimitError,
    ResponseError,
    TransportError,
    ValidationError,
)
from agentpost_sdk.models import (
    AgentProfile,
    ApprovalPage,
    ApprovalRequest,
    Attachment,
    DirectoryPage,
    DownloadedFile,
    InboxPage,
    Message,
)

__all__ = [
    "AgentPost",
    "AgentPostError",
    "ApiError",
    "AgentProfile",
    "ApprovalPage",
    "ApprovalRequest",
    "Attachment",
    "AuthenticationError",
    "AuthorizationError",
    "ConfigurationError",
    "ConflictError",
    "DirectoryPage",
    "DownloadedFile",
    "ForbiddenError",
    "InboxPage",
    "Message",
    "NotFoundError",
    "ProtocolError",
    "RateLimitError",
    "ResponseError",
    "TransportError",
    "ValidationError",
]

__version__ = "0.1.0"
