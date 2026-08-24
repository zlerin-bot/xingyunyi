from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agentpost.accounts.models import (
    HumanEmailChallenge,
    HumanPasswordCredential,
    HumanTotpCredential,
)
from agentpost.attachments.models import Attachment
from agentpost.config import Settings
from agentpost.control.models import (
    AgentOwnership,
    ApprovalDecision,
    ApprovalRequest,
    HumanAccessKey,
    HumanActionAudit,
    HumanActionConfirmation,
    HumanAgentGrant,
    HumanSession,
    HumanUser,
    Organization,
    OrganizationAgent,
    OrganizationMembership,
)
from agentpost.db import Base, Database
from agentpost.identity.models import Agent, AgentApiKey
from agentpost.main import create_app
from agentpost.messaging.models import AuditLog, Delivery, IdempotencyRecord, Message
from agentpost.oauth.models import OAuthAccessToken, OAuthRefreshToken
from agentpost.onboarding.models import (
    AgentConnectorBinding,
    AgentPairingSession,
    ConnectorInstance,
)
from agentpost.organizations.models import OrganizationDomain, OrganizationInvitation
from agentpost.security.models import RateLimitBucket
from agentpost.sso.models import OidcLoginState, OrganizationOidcIdentity, OrganizationOidcProvider

_MODELS = (
    Agent,
    AgentApiKey,
    Message,
    Delivery,
    IdempotencyRecord,
    AuditLog,
    Attachment,
    HumanUser,
    HumanAccessKey,
    AgentOwnership,
    HumanAgentGrant,
    HumanSession,
    HumanActionConfirmation,
    HumanActionAudit,
    Organization,
    OrganizationMembership,
    OrganizationAgent,
    ApprovalRequest,
    ApprovalDecision,
    ConnectorInstance,
    AgentConnectorBinding,
    AgentPairingSession,
    HumanPasswordCredential,
    HumanEmailChallenge,
    HumanTotpCredential,
    OrganizationInvitation,
    OrganizationDomain,
    OAuthAccessToken,
    OAuthRefreshToken,
    OrganizationOidcProvider,
    OrganizationOidcIdentity,
    OidcLoginState,
    RateLimitBucket,
)


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    return f"sqlite+pysqlite:///{tmp_path / 'agentpost-test.db'}"


@pytest.fixture
def settings(database_url: str, tmp_path: Path) -> Settings:
    return Settings(
        environment="test",
        database_url=database_url,
        storage_path=tmp_path / "attachments",
        api_key_pepper="test-pepper",
        log_level="WARNING",
    )


@pytest.fixture
def database(settings: Settings) -> Iterator[Database]:
    instance = Database(settings.database_url)
    Base.metadata.create_all(instance.engine)
    yield instance
    Base.metadata.drop_all(instance.engine)
    instance.dispose()


@pytest.fixture
def client(settings: Settings, database: Database) -> Iterator[TestClient]:
    app = create_app(settings=settings, database=database)
    with TestClient(app) as test_client:
        yield test_client
