from __future__ import annotations

from datetime import datetime
from uuid import UUID

from agentpost.identity.schemas import StrictModel


class AttachmentResponse(StrictModel):
    id: UUID
    filename: str
    content_type: str
    size: int
    sha256: str
    state: str
    created_at: datetime
