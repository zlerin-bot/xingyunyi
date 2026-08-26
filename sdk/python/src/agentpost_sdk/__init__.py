"""Framework-agnostic synchronous Python client for AgentPost."""

from agentpost_sdk.client import AgentPost
from agentpost_sdk.connector import (
    ConnectorCredential,
    ConnectorWorker,
    JsonCursorStore,
    KeyringCredentialStore,
    ManagedConnector,
    MemoryCursorStore,
)
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
    RecipientCandidate,
    RecipientResolution,
)
from agentpost_sdk.onboarding import (
    ConnectorCredentialRotation,
    ConnectorHeartbeat,
    PairingInstructions,
    PairingSession,
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
    "ConnectorCredentialRotation",
    "ConnectorCredential",
    "ConnectorHeartbeat",
    "ConnectorWorker",
    "ConflictError",
    "DirectoryPage",
    "DownloadedFile",
    "ForbiddenError",
    "InboxPage",
    "JsonCursorStore",
    "KeyringCredentialStore",
    "ManagedConnector",
    "MemoryCursorStore",
    "Message",
    "NotFoundError",
    "PairingInstructions",
    "PairingSession",
    "ProtocolError",
    "RateLimitError",
    "RecipientCandidate",
    "RecipientResolution",
    "ResponseError",
    "TransportError",
    "ValidationError",
]

__version__ = "0.1.14"
