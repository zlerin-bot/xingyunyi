from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agentpost.accounts.mailer import deliver_organization_invitation
from agentpost.config import Settings
from agentpost.control.human_security import add_human_action_audit
from agentpost.control.models import (
    HumanUser,
    Organization,
    OrganizationMembership,
)
from agentpost.control.organization_service import (
    list_organization_memberships,
    organization_response,
)
from agentpost.control.schemas import OrganizationCreate, OrganizationMembershipResponse
from agentpost.identity.models import utc_now
from agentpost.organizations.models import OrganizationDomain, OrganizationInvitation
from agentpost.organizations.schemas import (
    OrganizationCreateResponse,
    OrganizationDomainCreate,
    OrganizationDomainCreated,
    OrganizationDomainResponse,
    OrganizationInvitationAccepted,
    OrganizationInvitationCreate,
    OrganizationInvitationCreated,
    OrganizationInvitationPreview,
    OrganizationInvitationResponse,
)


class OrganizationAccessDeniedError(Exception):
    pass


class OrganizationSelfGovernanceNotFoundError(Exception):
    pass


class OrganizationSlugConflictError(Exception):
    pass


class OrganizationInvitationAlreadyPendingError(Exception):
    pass


class OrganizationInvitationInvalidError(Exception):
    pass


class OrganizationAlreadyMemberError(Exception):
    pass


class LastOrganizationOwnerError(Exception):
    pass


class OrganizationDomainConflictError(Exception):
    pass


class OrganizationDomainNotVerifiedError(Exception):
    pass


class OrganizationDomainLookupError(Exception):
    pass


@dataclass(frozen=True)
class OrganizationContext:
    organization: Organization
    membership: OrganizationMembership


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _membership_response(
    membership: OrganizationMembership,
    user: HumanUser,
) -> OrganizationMembershipResponse:
    return OrganizationMembershipResponse(
        organization_id=membership.organization_id,
        human_user_id=user.id,
        human_email=user.email,
        role=membership.role,
        created_at=_as_utc(membership.created_at),
        updated_at=_as_utc(membership.updated_at),
    )


def _invitation_response(invitation: OrganizationInvitation) -> OrganizationInvitationResponse:
    return OrganizationInvitationResponse(
        invitation_id=invitation.id,
        organization_id=invitation.organization_id,
        email=invitation.email,
        role=invitation.role,
        status=invitation.status,
        token_prefix=invitation.token_prefix,
        expires_at=_as_utc(invitation.expires_at),
        created_at=_as_utc(invitation.created_at),
    )


def _invitation_digest(raw_token: str, settings: Settings) -> str:
    return hmac.new(
        settings.human_auth_secret.get_secret_value().encode(),
        f"organization-invitation.{raw_token}".encode(),
        hashlib.sha256,
    ).hexdigest()


def _load_context(
    session: Session,
    *,
    organization_id: UUID,
    user: HumanUser,
    lock: bool = False,
) -> OrganizationContext:
    query = select(Organization).where(
        Organization.id == organization_id,
        Organization.status == "active",
    )
    if lock:
        query = query.with_for_update()
    organization = session.scalar(query)
    if organization is None:
        raise OrganizationSelfGovernanceNotFoundError
    membership = session.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization.id,
            OrganizationMembership.human_user_id == user.id,
        )
    )
    if membership is None:
        raise OrganizationSelfGovernanceNotFoundError
    return OrganizationContext(organization=organization, membership=membership)


def _require_manager(context: OrganizationContext) -> None:
    if context.membership.role not in {"owner", "admin"}:
        raise OrganizationAccessDeniedError


def _require_owner(context: OrganizationContext) -> None:
    if context.membership.role != "owner":
        raise OrganizationAccessDeniedError


def _domain_response(domain: OrganizationDomain) -> OrganizationDomainResponse:
    return OrganizationDomainResponse(
        domain_id=domain.id,
        organization_id=domain.organization_id,
        domain=domain.domain,
        status=domain.status,
        verification_record_name=f"_agentpost.{domain.domain}",
        verification_prefix=domain.verification_prefix,
        created_at=_as_utc(domain.created_at),
        last_checked_at=(
            _as_utc(domain.last_checked_at) if domain.last_checked_at is not None else None
        ),
        verified_at=_as_utc(domain.verified_at) if domain.verified_at is not None else None,
    )


def _domain_verification_digest(value: str, settings: Settings) -> str:
    return hmac.new(
        settings.human_auth_secret.get_secret_value().encode(),
        f"organization-domain.{value}".encode(),
        hashlib.sha256,
    ).hexdigest()


def lookup_dns_txt(record_name: str, *, timeout: float) -> list[str]:
    try:
        import dns.exception
        import dns.resolver

        answers = dns.resolver.resolve(record_name, "TXT", lifetime=timeout)
        values: list[str] = []
        for answer in answers:
            strings = getattr(answer, "strings", None)
            if strings is not None:
                values.append(b"".join(strings).decode("utf-8"))
            else:
                values.append(str(answer).strip('"').replace('" "', ""))
        return values
    except (ImportError, UnicodeDecodeError) as exc:
        raise OrganizationDomainLookupError from exc
    except (dns.exception.DNSException, OSError) as exc:
        raise OrganizationDomainLookupError from exc


def create_owned_organization(
    session: Session,
    *,
    user: HumanUser,
    payload: OrganizationCreate,
    human_session_id: UUID | None,
    request_id: str,
) -> OrganizationCreateResponse:
    now = utc_now()
    organization = Organization(
        slug=payload.slug,
        name=payload.name,
        description=payload.description,
        status="active",
        created_at=now,
        updated_at=now,
    )
    session.add(organization)
    try:
        session.flush()
        membership = OrganizationMembership(
            organization_id=organization.id,
            human_user_id=user.id,
            role="owner",
            created_at=now,
            updated_at=now,
        )
        session.add(membership)
        session.flush()
        add_human_action_audit(
            session,
            human_user_id=user.id,
            human_session_id=human_session_id,
            action="organization.created",
            target_type="organization",
            target_id=str(organization.id),
            outcome="success",
            request_id=request_id,
            audit_metadata={"slug": organization.slug, "role": "owner"},
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise OrganizationSlugConflictError from exc
    return OrganizationCreateResponse(
        organization=organization_response(session, organization),
        membership=_membership_response(membership, user),
    )


def create_invitation(
    session: Session,
    settings: Settings,
    *,
    user: HumanUser,
    organization_id: UUID,
    payload: OrganizationInvitationCreate,
    human_session_id: UUID | None,
    request_id: str,
) -> OrganizationInvitationCreated:
    context = _load_context(
        session,
        organization_id=organization_id,
        user=user,
        lock=True,
    )
    _require_manager(context)
    if context.membership.role == "admin" and payload.role == "admin":
        raise OrganizationAccessDeniedError
    existing_member = session.scalar(
        select(HumanUser.id)
        .join(
            OrganizationMembership,
            OrganizationMembership.human_user_id == HumanUser.id,
        )
        .where(
            OrganizationMembership.organization_id == organization_id,
            HumanUser.email == payload.email,
        )
    )
    if existing_member is not None:
        raise OrganizationAlreadyMemberError
    pending = session.scalar(
        select(OrganizationInvitation).where(
            OrganizationInvitation.organization_id == organization_id,
            OrganizationInvitation.email == payload.email,
            OrganizationInvitation.status == "pending",
        )
    )
    if pending is not None:
        if _as_utc(pending.expires_at) > utc_now():
            raise OrganizationInvitationAlreadyPendingError
        pending.status = "expired"
        session.flush()
    raw_token = f"orginv_{secrets.token_urlsafe(32)}"
    now = utc_now()
    invitation = OrganizationInvitation(
        organization_id=organization_id,
        email=payload.email,
        role=payload.role,
        token_digest=_invitation_digest(raw_token, settings),
        token_prefix=raw_token[:16],
        status="pending",
        invited_by_user_id=user.id,
        expires_at=now + timedelta(seconds=payload.expires_in_seconds),
        created_at=now,
    )
    session.add(invitation)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise OrganizationInvitationAlreadyPendingError from exc
    verification_uri = f"{settings.public_base_url}/orbit#organization-invitation={raw_token}"
    deliver_organization_invitation(
        settings,
        email=payload.email,
        organization_name=context.organization.name,
        verification_uri=verification_uri,
    )
    add_human_action_audit(
        session,
        human_user_id=user.id,
        human_session_id=human_session_id,
        action="organization.invitation_created",
        target_type="organization_invitation",
        target_id=str(invitation.id),
        outcome="success",
        request_id=request_id,
        audit_metadata={"organization_id": str(organization_id), "role": payload.role},
    )
    session.commit()
    return OrganizationInvitationCreated(
        invitation=_invitation_response(invitation),
        verification_uri=(verification_uri if settings.email_delivery_mode == "test" else None),
        test_acceptance_token=(raw_token if settings.email_delivery_mode == "test" else None),
    )


def list_invitations(
    session: Session,
    *,
    user: HumanUser,
    organization_id: UUID,
    limit: int,
) -> list[OrganizationInvitationResponse]:
    context = _load_context(session, organization_id=organization_id, user=user)
    _require_manager(context)
    invitations = session.scalars(
        select(OrganizationInvitation)
        .where(OrganizationInvitation.organization_id == organization_id)
        .order_by(OrganizationInvitation.created_at.desc())
        .limit(limit)
    ).all()
    now = utc_now()
    changed = False
    for invitation in invitations:
        if invitation.status == "pending" and _as_utc(invitation.expires_at) <= now:
            invitation.status = "expired"
            changed = True
    if changed:
        session.commit()
    return [_invitation_response(item) for item in invitations]


def list_members(
    session: Session,
    *,
    user: HumanUser,
    organization_id: UUID,
    limit: int,
) -> list[OrganizationMembershipResponse]:
    _load_context(session, organization_id=organization_id, user=user)
    return list_organization_memberships(
        session,
        organization_id=organization_id,
        limit=limit,
    )


def preview_invitation(
    session: Session,
    settings: Settings,
    *,
    user: HumanUser,
    raw_token: str,
) -> OrganizationInvitationPreview:
    if not raw_token.startswith("orginv_"):
        raise OrganizationInvitationInvalidError
    invitation = session.scalar(
        select(OrganizationInvitation).where(
            OrganizationInvitation.token_digest == _invitation_digest(raw_token, settings)
        )
    )
    now = utc_now()
    if (
        invitation is None
        or invitation.status != "pending"
        or _as_utc(invitation.expires_at) <= now
        or not hmac.compare_digest(invitation.email, user.email)
    ):
        raise OrganizationInvitationInvalidError
    organization = session.scalar(
        select(Organization).where(
            Organization.id == invitation.organization_id,
            Organization.status == "active",
        )
    )
    if organization is None:
        raise OrganizationInvitationInvalidError
    existing = session.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization.id,
            OrganizationMembership.human_user_id == user.id,
        )
    )
    if existing is not None:
        raise OrganizationAlreadyMemberError
    return OrganizationInvitationPreview(
        organization_id=organization.id,
        organization_slug=organization.slug,
        organization_name=organization.name,
        organization_description=organization.description,
        role=invitation.role,
        expires_at=_as_utc(invitation.expires_at),
    )


def accept_invitation(
    session: Session,
    settings: Settings,
    *,
    user: HumanUser,
    raw_token: str,
    human_session_id: UUID | None,
    request_id: str,
) -> OrganizationInvitationAccepted:
    if not raw_token.startswith("orginv_"):
        raise OrganizationInvitationInvalidError
    invitation = session.scalar(
        select(OrganizationInvitation)
        .where(OrganizationInvitation.token_digest == _invitation_digest(raw_token, settings))
        .with_for_update()
    )
    now = utc_now()
    if (
        invitation is None
        or invitation.status != "pending"
        or _as_utc(invitation.expires_at) <= now
        or not hmac.compare_digest(invitation.email, user.email)
    ):
        raise OrganizationInvitationInvalidError
    organization = session.scalar(
        select(Organization)
        .where(
            Organization.id == invitation.organization_id,
            Organization.status == "active",
        )
        .with_for_update()
    )
    if organization is None:
        raise OrganizationInvitationInvalidError
    existing = session.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization.id,
            OrganizationMembership.human_user_id == user.id,
        )
    )
    if existing is not None:
        raise OrganizationAlreadyMemberError
    membership = OrganizationMembership(
        organization_id=organization.id,
        human_user_id=user.id,
        role=invitation.role,
        created_at=now,
        updated_at=now,
    )
    session.add(membership)
    invitation.status = "accepted"
    invitation.accepted_at = now
    invitation.accepted_by_user_id = user.id
    session.flush()
    add_human_action_audit(
        session,
        human_user_id=user.id,
        human_session_id=human_session_id,
        action="organization.invitation_accepted",
        target_type="organization_invitation",
        target_id=str(invitation.id),
        outcome="success",
        request_id=request_id,
        audit_metadata={"organization_id": str(organization.id), "role": membership.role},
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise OrganizationAlreadyMemberError from exc
    return OrganizationInvitationAccepted(
        organization=organization_response(session, organization),
        membership=_membership_response(membership, user),
    )


def revoke_invitation(
    session: Session,
    *,
    user: HumanUser,
    organization_id: UUID,
    invitation_id: UUID,
    human_session_id: UUID | None,
    request_id: str,
) -> None:
    context = _load_context(
        session,
        organization_id=organization_id,
        user=user,
        lock=True,
    )
    _require_manager(context)
    invitation = session.scalar(
        select(OrganizationInvitation)
        .where(
            OrganizationInvitation.id == invitation_id,
            OrganizationInvitation.organization_id == organization_id,
            OrganizationInvitation.status == "pending",
        )
        .with_for_update()
    )
    if invitation is None:
        raise OrganizationSelfGovernanceNotFoundError
    invitation.status = "revoked"
    invitation.revoked_at = utc_now()
    add_human_action_audit(
        session,
        human_user_id=user.id,
        human_session_id=human_session_id,
        action="organization.invitation_revoked",
        target_type="organization_invitation",
        target_id=str(invitation.id),
        outcome="success",
        request_id=request_id,
        audit_metadata={"organization_id": str(organization_id)},
    )
    session.commit()


def _owner_count(session: Session, organization_id: UUID) -> int:
    return int(
        session.scalar(
            select(func.count(OrganizationMembership.id)).where(
                OrganizationMembership.organization_id == organization_id,
                OrganizationMembership.role == "owner",
            )
        )
        or 0
    )


def change_member_role(
    session: Session,
    *,
    actor: HumanUser,
    organization_id: UUID,
    member_user_id: UUID,
    role: str,
    human_session_id: UUID | None,
    request_id: str,
) -> OrganizationMembershipResponse:
    context = _load_context(
        session,
        organization_id=organization_id,
        user=actor,
        lock=True,
    )
    _require_manager(context)
    target = session.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.human_user_id == member_user_id,
        )
    )
    target_user = session.get(HumanUser, member_user_id)
    if target is None or target_user is None:
        raise OrganizationSelfGovernanceNotFoundError
    if context.membership.role == "admin" and (
        target.role in {"owner", "admin"} or role in {"owner", "admin"}
    ):
        raise OrganizationAccessDeniedError
    if target.role == "owner" and role != "owner" and _owner_count(session, organization_id) <= 1:
        raise LastOrganizationOwnerError
    target.role = role
    target.updated_at = utc_now()
    add_human_action_audit(
        session,
        human_user_id=actor.id,
        human_session_id=human_session_id,
        action="organization.member_role_changed",
        target_type="organization_membership",
        target_id=str(target.id),
        outcome="success",
        request_id=request_id,
        audit_metadata={"organization_id": str(organization_id), "role": role},
    )
    session.commit()
    return _membership_response(target, target_user)


def remove_member(
    session: Session,
    *,
    actor: HumanUser,
    organization_id: UUID,
    member_user_id: UUID,
    human_session_id: UUID | None,
    request_id: str,
    self_exit: bool = False,
) -> None:
    context = _load_context(
        session,
        organization_id=organization_id,
        user=actor,
        lock=True,
    )
    if not self_exit:
        _require_manager(context)
    target = session.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.human_user_id == member_user_id,
        )
    )
    if target is None or (self_exit and member_user_id != actor.id):
        raise OrganizationSelfGovernanceNotFoundError
    if not self_exit and context.membership.role == "admin" and target.role in {"owner", "admin"}:
        raise OrganizationAccessDeniedError
    if target.role == "owner" and _owner_count(session, organization_id) <= 1:
        raise LastOrganizationOwnerError
    target_id = str(target.id)
    session.delete(target)
    add_human_action_audit(
        session,
        human_user_id=actor.id,
        human_session_id=human_session_id,
        action="organization.member_left" if self_exit else "organization.member_removed",
        target_type="organization_membership",
        target_id=target_id,
        outcome="success",
        request_id=request_id,
        audit_metadata={"organization_id": str(organization_id)},
    )
    session.commit()


def create_domain_claim(
    session: Session,
    settings: Settings,
    *,
    user: HumanUser,
    organization_id: UUID,
    payload: OrganizationDomainCreate,
    human_session_id: UUID | None,
    request_id: str,
) -> OrganizationDomainCreated:
    context = _load_context(
        session,
        organization_id=organization_id,
        user=user,
        lock=True,
    )
    _require_owner(context)
    existing = session.scalar(
        select(OrganizationDomain).where(OrganizationDomain.domain == payload.domain)
    )
    if (
        existing is not None
        and existing.status != "revoked"
        and (existing.organization_id != organization_id or existing.status == "verified")
    ):
        raise OrganizationDomainConflictError
    raw_value = f"agentpost-domain-verification={secrets.token_urlsafe(32)}"
    now = utc_now()
    if existing is None:
        domain = OrganizationDomain(
            organization_id=organization_id,
            domain=payload.domain,
            status="pending",
            verification_digest=_domain_verification_digest(raw_value, settings),
            verification_prefix=raw_value[-10:],
            created_by_user_id=user.id,
            created_at=now,
        )
        session.add(domain)
    else:
        domain = existing
        domain.organization_id = organization_id
        domain.status = "pending"
        domain.verification_digest = _domain_verification_digest(raw_value, settings)
        domain.verification_prefix = raw_value[-10:]
        domain.created_by_user_id = user.id
        domain.last_checked_at = None
        domain.verified_at = None
        domain.revoked_at = None
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise OrganizationDomainConflictError from exc
    add_human_action_audit(
        session,
        human_user_id=user.id,
        human_session_id=human_session_id,
        action="organization.domain_claim_created",
        target_type="organization_domain",
        target_id=str(domain.id),
        outcome="success",
        request_id=request_id,
        audit_metadata={"organization_id": str(organization_id), "domain": domain.domain},
    )
    session.commit()
    return OrganizationDomainCreated(
        domain=_domain_response(domain),
        verification_value=raw_value,
    )


def list_domains(
    session: Session,
    *,
    user: HumanUser,
    organization_id: UUID,
) -> list[OrganizationDomainResponse]:
    _load_context(session, organization_id=organization_id, user=user)
    domains = session.scalars(
        select(OrganizationDomain)
        .where(
            OrganizationDomain.organization_id == organization_id,
            OrganizationDomain.status != "revoked",
        )
        .order_by(OrganizationDomain.domain)
    ).all()
    return [_domain_response(domain) for domain in domains]


def verify_domain_claim(
    session: Session,
    settings: Settings,
    *,
    user: HumanUser,
    organization_id: UUID,
    domain_id: UUID,
    human_session_id: UUID | None,
    request_id: str,
) -> OrganizationDomainResponse:
    context = _load_context(
        session,
        organization_id=organization_id,
        user=user,
        lock=True,
    )
    _require_owner(context)
    domain = session.scalar(
        select(OrganizationDomain)
        .where(
            OrganizationDomain.id == domain_id,
            OrganizationDomain.organization_id == organization_id,
            OrganizationDomain.status != "revoked",
        )
        .with_for_update()
    )
    if domain is None:
        raise OrganizationSelfGovernanceNotFoundError
    if domain.status == "verified":
        return _domain_response(domain)
    values = lookup_dns_txt(
        f"_agentpost.{domain.domain}",
        timeout=settings.domain_verification_timeout_seconds,
    )
    now = utc_now()
    domain.last_checked_at = now
    matched = any(
        hmac.compare_digest(
            _domain_verification_digest(value, settings),
            domain.verification_digest,
        )
        for value in values
    )
    if not matched:
        session.commit()
        raise OrganizationDomainNotVerifiedError
    domain.status = "verified"
    domain.verified_at = now
    add_human_action_audit(
        session,
        human_user_id=user.id,
        human_session_id=human_session_id,
        action="organization.domain_verified",
        target_type="organization_domain",
        target_id=str(domain.id),
        outcome="success",
        request_id=request_id,
        audit_metadata={"organization_id": str(organization_id), "domain": domain.domain},
    )
    session.commit()
    return _domain_response(domain)


def revoke_domain_claim(
    session: Session,
    *,
    user: HumanUser,
    organization_id: UUID,
    domain_id: UUID,
    human_session_id: UUID | None,
    request_id: str,
) -> None:
    context = _load_context(
        session,
        organization_id=organization_id,
        user=user,
        lock=True,
    )
    _require_owner(context)
    domain = session.scalar(
        select(OrganizationDomain)
        .where(
            OrganizationDomain.id == domain_id,
            OrganizationDomain.organization_id == organization_id,
            OrganizationDomain.status != "revoked",
        )
        .with_for_update()
    )
    if domain is None:
        raise OrganizationSelfGovernanceNotFoundError
    domain.status = "revoked"
    domain.revoked_at = utc_now()
    add_human_action_audit(
        session,
        human_user_id=user.id,
        human_session_id=human_session_id,
        action="organization.domain_revoked",
        target_type="organization_domain",
        target_id=str(domain.id),
        outcome="success",
        request_id=request_id,
        audit_metadata={"organization_id": str(organization_id), "domain": domain.domain},
    )
    session.commit()
