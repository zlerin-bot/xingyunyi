from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode, urlsplit
from uuid import UUID

import httpx
import jwt
from cryptography.fernet import InvalidToken
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agentpost.accounts.crypto import (
    decrypt_application_secret,
    encrypt_application_secret,
)
from agentpost.accounts.schemas import EmailChallengeStart, PasswordMfaProof
from agentpost.accounts.service import verify_password_and_mfa
from agentpost.config import Settings
from agentpost.control.human_security import add_human_action_audit
from agentpost.control.models import (
    HumanUser,
    Organization,
    OrganizationMembership,
)
from agentpost.identity.models import utc_now
from agentpost.messaging.models import AuditLog
from agentpost.organizations.models import OrganizationDomain
from agentpost.sso.models import (
    OidcLoginState,
    OrganizationOidcIdentity,
    OrganizationOidcProvider,
)
from agentpost.sso.schemas import (
    OidcLoginStartResponse,
    OidcProviderCreate,
    OidcProviderResponse,
)

OIDC_STATE_MARKER = "oidcs_"
OIDC_NONCE_MARKER = "oidcn_"
OIDC_ALLOWED_ALGORITHMS = frozenset({"RS256", "ES256"})


class OidcDisabledError(Exception):
    pass


class OidcProviderNotFoundError(Exception):
    pass


class OidcAccessDeniedError(Exception):
    pass


class OidcIssuerNotAllowedError(Exception):
    pass


class OidcVerifiedDomainRequiredError(Exception):
    pass


class OidcProviderConflictError(Exception):
    pass


class OidcProviderConfigurationError(Exception):
    pass


class OidcStateInvalidError(Exception):
    pass


class OidcTokenExchangeError(Exception):
    pass


class OidcClaimsInvalidError(Exception):
    pass


class OidcAccountLinkRequiredError(Exception):
    pass


@dataclass(frozen=True)
class OidcAuthentication:
    user: HumanUser
    mfa_authenticated: bool


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _digest(label: str, raw_value: str, settings: Settings) -> str:
    return hmac.new(
        settings.human_auth_secret.get_secret_value().encode(),
        f"oidc.{label}.{raw_value}".encode(),
        hashlib.sha256,
    ).hexdigest()


def _provider_response(provider: OrganizationOidcProvider) -> OidcProviderResponse:
    return OidcProviderResponse(
        provider_id=provider.id,
        organization_id=provider.organization_id,
        display_name=provider.display_name,
        issuer=provider.issuer,
        client_id=provider.client_id,
        status=provider.status,
        created_at=_as_utc(provider.created_at),
        updated_at=_as_utc(provider.updated_at),
    )


def _require_oidc(settings: Settings) -> None:
    if not settings.enterprise_oidc_enabled:
        raise OidcDisabledError


def _load_organization_owner(
    session: Session,
    *,
    organization_id: UUID,
    user: HumanUser,
) -> Organization:
    organization = session.get(Organization, organization_id)
    membership = session.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.human_user_id == user.id,
        )
    )
    if organization is None or organization.status != "active" or membership is None:
        raise OidcProviderNotFoundError
    if membership.role != "owner":
        raise OidcAccessDeniedError
    return organization


def _has_verified_domain(session: Session, organization_id: UUID) -> bool:
    return (
        session.scalar(
            select(OrganizationDomain.id).where(
                OrganizationDomain.organization_id == organization_id,
                OrganizationDomain.status == "verified",
            )
        )
        is not None
    )


def _safe_endpoint(value: object, *, issuer: str) -> str:
    if not isinstance(value, str):
        raise OidcProviderConfigurationError
    endpoint = value.strip()
    parsed = urlsplit(endpoint)
    issuer_parsed = urlsplit(issuer)
    if (
        parsed.scheme != issuer_parsed.scheme
        or parsed.hostname != issuer_parsed.hostname
        or parsed.port != issuer_parsed.port
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise OidcProviderConfigurationError
    return endpoint


def _issuer_is_safe(issuer: str, settings: Settings) -> bool:
    if issuer not in settings.allowed_oidc_issuers:
        return False
    parsed = urlsplit(issuer)
    if not parsed.hostname:
        return False
    if parsed.hostname.casefold() == "localhost":
        return False
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        return True
    return address.is_global


def _http_client(settings: Settings, transport: httpx.BaseTransport | None) -> httpx.Client:
    return httpx.Client(
        timeout=settings.oidc_http_timeout_seconds,
        follow_redirects=False,
        transport=transport,
        headers={"User-Agent": "AgentPost-OIDC/0.1"},
    )


def _load_discovery(
    settings: Settings,
    *,
    issuer: str,
    transport: httpx.BaseTransport | None,
) -> dict[str, Any]:
    discovery_url = f"{issuer}/.well-known/openid-configuration"
    try:
        with _http_client(settings, transport) as client:
            response = client.get(discovery_url)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise OidcProviderConfigurationError from exc
    if not isinstance(payload, dict) or payload.get("issuer") != issuer:
        raise OidcProviderConfigurationError
    methods = payload.get("token_endpoint_auth_methods_supported")
    if not isinstance(methods, list) or "client_secret_post" not in methods:
        raise OidcProviderConfigurationError
    return payload


def create_provider(
    session: Session,
    settings: Settings,
    *,
    organization_id: UUID,
    user: HumanUser,
    payload: OidcProviderCreate,
    human_session_id: UUID | None,
    request_id: str,
    transport: httpx.BaseTransport | None = None,
) -> OidcProviderResponse:
    _require_oidc(settings)
    _load_organization_owner(session, organization_id=organization_id, user=user)
    if not _has_verified_domain(session, organization_id):
        raise OidcVerifiedDomainRequiredError
    if not _issuer_is_safe(payload.issuer, settings):
        raise OidcIssuerNotAllowedError
    discovery = _load_discovery(settings, issuer=payload.issuer, transport=transport)
    authorization_endpoint = _safe_endpoint(
        discovery.get("authorization_endpoint"), issuer=payload.issuer
    )
    token_endpoint = _safe_endpoint(discovery.get("token_endpoint"), issuer=payload.issuer)
    jwks_uri = _safe_endpoint(discovery.get("jwks_uri"), issuer=payload.issuer)
    now = utc_now()
    provider = OrganizationOidcProvider(
        organization_id=organization_id,
        display_name=payload.display_name,
        issuer=payload.issuer,
        client_id=payload.client_id,
        encrypted_client_secret=encrypt_application_secret(
            payload.client_secret.get_secret_value(),
            settings.human_mfa_encryption_key,
        ),
        scopes="openid email profile",
        authorization_endpoint=authorization_endpoint,
        token_endpoint=token_endpoint,
        jwks_uri=jwks_uri,
        status="active",
        created_by_user_id=user.id,
        created_at=now,
        updated_at=now,
    )
    session.add(provider)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise OidcProviderConflictError from exc
    add_human_action_audit(
        session,
        human_user_id=user.id,
        human_session_id=human_session_id,
        action="organization.oidc_provider_created",
        target_type="organization_oidc_provider",
        target_id=str(provider.id),
        outcome="success",
        request_id=request_id,
        audit_metadata={"organization_id": str(organization_id), "issuer": provider.issuer},
    )
    session.commit()
    return _provider_response(provider)


def list_providers(
    session: Session,
    settings: Settings,
    *,
    organization_id: UUID,
    user: HumanUser,
) -> list[OidcProviderResponse]:
    _require_oidc(settings)
    _load_organization_owner(session, organization_id=organization_id, user=user)
    providers = session.scalars(
        select(OrganizationOidcProvider)
        .where(OrganizationOidcProvider.organization_id == organization_id)
        .order_by(OrganizationOidcProvider.created_at)
    ).all()
    return [_provider_response(provider) for provider in providers]


def disable_provider(
    session: Session,
    settings: Settings,
    *,
    organization_id: UUID,
    provider_id: UUID,
    user: HumanUser,
    human_session_id: UUID | None,
    request_id: str,
) -> None:
    _require_oidc(settings)
    _load_organization_owner(session, organization_id=organization_id, user=user)
    provider = session.scalar(
        select(OrganizationOidcProvider)
        .where(
            OrganizationOidcProvider.id == provider_id,
            OrganizationOidcProvider.organization_id == organization_id,
        )
        .with_for_update()
    )
    if provider is None:
        raise OidcProviderNotFoundError
    if provider.status != "disabled":
        provider.status = "disabled"
        provider.disabled_at = utc_now()
        provider.updated_at = provider.disabled_at
        add_human_action_audit(
            session,
            human_user_id=user.id,
            human_session_id=human_session_id,
            action="organization.oidc_provider_disabled",
            target_type="organization_oidc_provider",
            target_id=str(provider.id),
            outcome="success",
            request_id=request_id,
            audit_metadata={"organization_id": str(organization_id)},
        )
        session.commit()


def discover_providers(
    session: Session,
    settings: Settings,
    *,
    email: str,
) -> list[OidcProviderResponse]:
    _require_oidc(settings)
    domain = email.rsplit("@", 1)[1]
    providers = session.scalars(
        select(OrganizationOidcProvider)
        .join(
            OrganizationDomain,
            OrganizationDomain.organization_id == OrganizationOidcProvider.organization_id,
        )
        .where(
            OrganizationOidcProvider.status == "active",
            OrganizationDomain.domain == domain,
            OrganizationDomain.status == "verified",
        )
        .order_by(OrganizationOidcProvider.display_name)
    ).all()
    return [_provider_response(provider) for provider in providers]


def _create_login_state(
    session: Session,
    settings: Settings,
    *,
    provider: OrganizationOidcProvider,
    link_human_user_id: UUID | None,
    request_id: str,
) -> OidcLoginStartResponse:
    raw_state = f"{OIDC_STATE_MARKER}{secrets.token_urlsafe(32)}"
    raw_nonce = f"{OIDC_NONCE_MARKER}{secrets.token_urlsafe(32)}"
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    now = utc_now()
    expires_at = now + timedelta(seconds=settings.oidc_state_ttl_seconds)
    state = OidcLoginState(
        state_digest=_digest("state", raw_state, settings),
        provider_id=provider.id,
        encrypted_code_verifier=encrypt_application_secret(
            code_verifier,
            settings.human_mfa_encryption_key,
        ),
        nonce_digest=_digest("nonce", raw_nonce, settings),
        link_human_user_id=link_human_user_id,
        expires_at=expires_at,
        created_at=now,
    )
    session.add(state)
    session.add(
        AuditLog(
            actor_agent_id=None,
            action="account.oidc_login_started",
            target_type="organization_oidc_provider",
            target_id=str(provider.id),
            outcome="success",
            request_id=request_id,
            audit_metadata={"link_existing": link_human_user_id is not None},
            created_at=now,
        )
    )
    session.commit()
    redirect_uri = f"{settings.public_base_url}/api/v1/auth/oidc/callback"
    query = urlencode(
        {
            "client_id": provider.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": provider.scopes,
            "state": raw_state,
            "nonce": raw_nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
    )
    separator = "&" if "?" in provider.authorization_endpoint else "?"
    return OidcLoginStartResponse(
        authorization_url=f"{provider.authorization_endpoint}{separator}{query}",
        expires_at=expires_at,
    )


def start_login(
    session: Session,
    settings: Settings,
    *,
    provider_id: UUID,
    request_id: str,
) -> OidcLoginStartResponse:
    _require_oidc(settings)
    provider = session.scalar(
        select(OrganizationOidcProvider).where(
            OrganizationOidcProvider.id == provider_id,
            OrganizationOidcProvider.status == "active",
        )
    )
    if provider is None or not _has_verified_domain(session, provider.organization_id):
        raise OidcProviderNotFoundError
    return _create_login_state(
        session,
        settings,
        provider=provider,
        link_human_user_id=None,
        request_id=request_id,
    )


def start_account_link(
    session: Session,
    settings: Settings,
    *,
    organization_id: UUID,
    provider_id: UUID,
    user: HumanUser,
    proof: PasswordMfaProof,
    request_id: str,
) -> OidcLoginStartResponse:
    _require_oidc(settings)
    membership = session.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.human_user_id == user.id,
        )
    )
    provider = session.scalar(
        select(OrganizationOidcProvider).where(
            OrganizationOidcProvider.id == provider_id,
            OrganizationOidcProvider.organization_id == organization_id,
            OrganizationOidcProvider.status == "active",
        )
    )
    if membership is None or provider is None:
        raise OidcProviderNotFoundError
    verify_password_and_mfa(
        session,
        settings,
        user=user,
        password=proof.password.get_secret_value(),
        totp_code=proof.totp_code,
        recovery_code=proof.recovery_code,
    )
    return _create_login_state(
        session,
        settings,
        provider=provider,
        link_human_user_id=user.id,
        request_id=request_id,
    )


def _consume_state(
    session: Session,
    settings: Settings,
    raw_state: str,
) -> tuple[OidcLoginState, OrganizationOidcProvider, str]:
    if not raw_state.startswith(OIDC_STATE_MARKER):
        raise OidcStateInvalidError
    state = session.scalar(
        select(OidcLoginState)
        .where(OidcLoginState.state_digest == _digest("state", raw_state, settings))
        .with_for_update()
    )
    now = utc_now()
    if state is None or state.consumed_at is not None or _as_utc(state.expires_at) <= now:
        raise OidcStateInvalidError
    provider = session.get(OrganizationOidcProvider, state.provider_id)
    if provider is None or provider.status != "active":
        raise OidcStateInvalidError
    try:
        code_verifier = decrypt_application_secret(
            state.encrypted_code_verifier,
            settings.human_mfa_encryption_key,
        )
    except InvalidToken as exc:
        raise OidcStateInvalidError from exc
    state.consumed_at = now
    session.commit()
    return state, provider, code_verifier


def _exchange_and_verify(
    settings: Settings,
    *,
    state: OidcLoginState,
    provider: OrganizationOidcProvider,
    code: str,
    code_verifier: str,
    transport: httpx.BaseTransport | None,
) -> dict[str, Any]:
    try:
        client_secret = decrypt_application_secret(
            provider.encrypted_client_secret,
            settings.human_mfa_encryption_key,
        )
    except InvalidToken as exc:
        raise OidcTokenExchangeError from exc
    redirect_uri = f"{settings.public_base_url}/api/v1/auth/oidc/callback"
    try:
        with _http_client(settings, transport) as client:
            token_response = client.post(
                provider.token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": provider.client_id,
                    "client_secret": client_secret,
                    "code_verifier": code_verifier,
                },
            )
            token_response.raise_for_status()
            token_payload = token_response.json()
            id_token = token_payload.get("id_token")
            if not isinstance(id_token, str):
                raise OidcTokenExchangeError
            jwks_response = client.get(provider.jwks_uri)
            jwks_response.raise_for_status()
            jwks = jwks_response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise OidcTokenExchangeError from exc
    try:
        header = jwt.get_unverified_header(id_token)
        algorithm = header.get("alg")
        key_id = header.get("kid")
        if algorithm not in OIDC_ALLOWED_ALGORITHMS or not isinstance(key_id, str):
            raise OidcClaimsInvalidError
        keys = jwks.get("keys") if isinstance(jwks, dict) else None
        if not isinstance(keys, list):
            raise OidcClaimsInvalidError
        key_data = next(
            (item for item in keys if isinstance(item, dict) and item.get("kid") == key_id),
            None,
        )
        if key_data is None:
            raise OidcClaimsInvalidError
        public_key = jwt.PyJWK.from_dict(key_data, algorithm=algorithm).key
        claims = jwt.decode(
            id_token,
            public_key,
            algorithms=[algorithm],
            audience=provider.client_id,
            issuer=provider.issuer,
            leeway=60,
            options={"require": ["exp", "iat", "sub", "nonce", "email", "email_verified"]},
        )
    except (InvalidTokenError, ValueError, StopIteration) as exc:
        raise OidcClaimsInvalidError from exc
    nonce = claims.get("nonce")
    if not isinstance(nonce, str) or not hmac.compare_digest(
        state.nonce_digest,
        _digest("nonce", nonce, settings),
    ):
        raise OidcClaimsInvalidError
    if claims.get("email_verified") is not True:
        raise OidcClaimsInvalidError
    return claims


def _canonical_claim_email(value: object) -> str:
    if not isinstance(value, str):
        raise OidcClaimsInvalidError
    try:
        email = EmailChallengeStart.canonical_email(value)
    except ValueError as exc:
        raise OidcClaimsInvalidError from exc
    if not email.isascii():
        raise OidcClaimsInvalidError
    return email


def _verified_for_provider(
    session: Session,
    provider: OrganizationOidcProvider,
    email: str,
) -> bool:
    domain = email.rsplit("@", 1)[1]
    return (
        session.scalar(
            select(OrganizationDomain.id).where(
                OrganizationDomain.organization_id == provider.organization_id,
                OrganizationDomain.domain == domain,
                OrganizationDomain.status == "verified",
            )
        )
        is not None
    )


def _complete_identity(
    session: Session,
    *,
    state: OidcLoginState,
    provider: OrganizationOidcProvider,
    claims: dict[str, Any],
    request_id: str,
) -> HumanUser:
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject or len(subject) > 512:
        raise OidcClaimsInvalidError
    email = _canonical_claim_email(claims.get("email"))
    if not _verified_for_provider(session, provider, email):
        raise OidcClaimsInvalidError
    identity = session.scalar(
        select(OrganizationOidcIdentity).where(
            OrganizationOidcIdentity.provider_id == provider.id,
            OrganizationOidcIdentity.subject == subject,
        )
    )
    now = utc_now()
    newly_provisioned = False
    if identity is not None:
        if (
            state.link_human_user_id is not None
            and identity.human_user_id != state.link_human_user_id
        ):
            raise OidcClaimsInvalidError
        user = session.get(HumanUser, identity.human_user_id)
        if user is None or user.status != "active" or user.email != email:
            raise OidcClaimsInvalidError
    elif state.link_human_user_id is not None:
        user = session.get(HumanUser, state.link_human_user_id)
        if user is None or user.status != "active" or user.email != email:
            raise OidcClaimsInvalidError
        identity = OrganizationOidcIdentity(
            provider_id=provider.id,
            subject=subject,
            human_user_id=user.id,
            email_at_link=email,
            created_at=now,
        )
        session.add(identity)
    else:
        user = session.scalar(select(HumanUser).where(HumanUser.email == email))
        if user is not None:
            raise OidcAccountLinkRequiredError
        raw_name = claims.get("name")
        display_name = (
            raw_name.strip()[:200]
            if isinstance(raw_name, str) and raw_name.strip()
            else email.split("@", 1)[0][:200]
        )
        user = HumanUser(
            email=email,
            display_name=display_name,
            status="active",
            email_verified_at=now,
            created_at=now,
            updated_at=now,
        )
        session.add(user)
        session.flush()
        newly_provisioned = True
        identity = OrganizationOidcIdentity(
            provider_id=provider.id,
            subject=subject,
            human_user_id=user.id,
            email_at_link=email,
            created_at=now,
        )
        session.add(identity)
    membership = session.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == provider.organization_id,
            OrganizationMembership.human_user_id == user.id,
        )
    )
    if membership is None:
        if not newly_provisioned:
            raise OidcAccessDeniedError
        session.add(
            OrganizationMembership(
                organization_id=provider.organization_id,
                human_user_id=user.id,
                role="member",
                created_at=now,
                updated_at=now,
            )
        )
    identity.last_login_at = now
    session.add(
        AuditLog(
            actor_agent_id=None,
            action="account.oidc_login_succeeded",
            target_type="human_user",
            target_id=str(user.id),
            outcome="success",
            request_id=request_id,
            audit_metadata={
                "provider_id": str(provider.id),
                "organization_id": str(provider.organization_id),
            },
            created_at=now,
        )
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise OidcClaimsInvalidError from exc
    return user


def complete_login(
    session: Session,
    settings: Settings,
    *,
    raw_state: str,
    code: str,
    request_id: str,
    transport: httpx.BaseTransport | None = None,
) -> OidcAuthentication:
    _require_oidc(settings)
    state, provider, code_verifier = _consume_state(session, settings, raw_state)
    claims = _exchange_and_verify(
        settings,
        state=state,
        provider=provider,
        code=code,
        code_verifier=code_verifier,
        transport=transport,
    )
    user = _complete_identity(
        session,
        state=state,
        provider=provider,
        claims=claims,
        request_id=request_id,
    )
    amr = claims.get("amr")
    mfa_authenticated = isinstance(amr, list) and any(
        isinstance(item, str) and item.casefold() in {"mfa", "otp", "hwk", "swk", "fido"}
        for item in amr
    )
    return OidcAuthentication(user=user, mfa_authenticated=mfa_authenticated)
