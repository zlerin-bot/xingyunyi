from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from agentpost.access.models import AccessRule
from agentpost.accounts.models import (
    HumanEmailChallenge,
    HumanPasswordCredential,
    HumanTotpCredential,
)
from agentpost.attachments.models import Attachment
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
from agentpost.db import Base
from agentpost.identity.models import Agent, AgentApiKey
from agentpost.messaging.models import AuditLog, Delivery, IdempotencyRecord, Message
from agentpost.oauth.models import OAuthAccessToken, OAuthRefreshToken
from agentpost.onboarding.models import (
    AgentConnectorBinding,
    AgentPairingSession,
    ConnectorInstance,
)
from agentpost.organizations.models import OrganizationDomain, OrganizationInvitation
from agentpost.sso.models import OidcLoginState, OrganizationOidcIdentity, OrganizationOidcProvider

_MODELS = (
    Agent,
    AgentApiKey,
    Message,
    Delivery,
    IdempotencyRecord,
    AuditLog,
    Attachment,
    AccessRule,
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
)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

database_url = os.getenv("AGENTPOST_DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
