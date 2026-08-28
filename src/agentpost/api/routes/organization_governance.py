from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Request, status

from agentpost.accounts.mailer import EmailDeliveryError
from agentpost.accounts.service import (
    AuthenticationFailedError,
    MfaInvalidError,
    MfaRequiredError,
    PasswordNotConfiguredError,
    verify_human_reauthentication,
)
from agentpost.api.dependencies import SessionDep, SettingsDep
from agentpost.control.auth import CurrentHumanDep
from agentpost.control.human_security import (
    HUMAN_CONFIRMATION_HEADER,
    HumanConfirmationInvalidError,
    HumanCsrfDep,
    consume_human_confirmation,
    create_human_confirmation,
    human_session_id_from_request,
)
from agentpost.control.models import HumanSession
from agentpost.control.schemas import (
    OrganizationAgentResponse,
    OrganizationCreate,
    OrganizationMembershipResponse,
)
from agentpost.organizations.schemas import (
    OrganizationAgentConfirmationCreate,
    OrganizationAgentConfirmationResponse,
    OrganizationCreateResponse,
    OrganizationDomainCreate,
    OrganizationDomainCreated,
    OrganizationDomainResponse,
    OrganizationInvitationAccept,
    OrganizationInvitationAccepted,
    OrganizationInvitationCreate,
    OrganizationInvitationCreated,
    OrganizationInvitationPreview,
    OrganizationInvitationResponse,
    OrganizationMembershipUpdate,
)
from agentpost.organizations.service import (
    LastOrganizationOwnerError,
    OrganizationAccessDeniedError,
    OrganizationAgentAlreadyAssignedError,
    OrganizationAgentAssignmentNotFoundError,
    OrganizationAgentOwnershipRequiredError,
    OrganizationAlreadyMemberError,
    OrganizationDomainConflictError,
    OrganizationDomainLookupError,
    OrganizationDomainNotVerifiedError,
    OrganizationInvitationAlreadyPendingError,
    OrganizationInvitationInvalidError,
    OrganizationSelfGovernanceNotFoundError,
    OrganizationSlugConflictError,
    accept_invitation,
    assign_owned_agent,
    authorize_owned_agent_management,
    change_member_role,
    create_domain_claim,
    create_invitation,
    create_owned_organization,
    list_domains,
    list_invitations,
    list_members,
    preview_invitation,
    remove_member,
    remove_owned_agent,
    revoke_domain_claim,
    revoke_invitation,
    verify_domain_claim,
)

router = APIRouter(prefix="/api/v1/orbit", tags=["organization-governance"])
Limit = Annotated[int, Query(ge=1, le=200)]


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "organization_not_found", "message": "Organization not found"},
    )


def _forbidden() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "organization_management_forbidden",
            "message": "The current organization role cannot perform this action",
        },
    )


def _agent_management_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "organization_agent_not_found", "message": "Agent was not found"},
    )


def _organization_agent_confirmation_target(organization_id: UUID, agent_id: UUID) -> str:
    return f"{organization_id}:{agent_id}"


def _verify_password_reauthentication(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    current_human: CurrentHumanDep,
    *,
    password: str,
) -> None:
    human_session_id = human_session_id_from_request(request)
    browser_session = session.get(HumanSession, human_session_id) if human_session_id else None
    session_mfa_authenticated = bool(
        browser_session
        and browser_session.human_user_id == current_human.id
        and browser_session.mfa_authenticated_at is not None
    )
    try:
        verify_human_reauthentication(
            session,
            settings,
            user=current_human,
            access_key_user=None,
            password=password,
            totp_code=None,
            recovery_code=None,
            session_mfa_authenticated=session_mfa_authenticated,
        )
    except (
        AuthenticationFailedError,
        MfaRequiredError,
        MfaInvalidError,
        PasswordNotConfiguredError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "human_reauthentication_failed",
                "message": "Current password and an MFA-authenticated session are required",
            },
        ) from exc


@router.post(
    "/organizations",
    response_model=OrganizationCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_human_organization(
    payload: OrganizationCreate,
    request: Request,
    current_human: CurrentHumanDep,
    session: SessionDep,
    csrf_guard: HumanCsrfDep,
) -> OrganizationCreateResponse:
    del csrf_guard
    try:
        return create_owned_organization(
            session,
            user=current_human,
            payload=payload,
            human_session_id=human_session_id_from_request(request),
            request_id=request.state.request_id,
        )
    except OrganizationSlugConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "organization_slug_already_registered"},
        ) from exc


@router.get(
    "/organizations/{organization_id}/members",
    response_model=dict[str, list[OrganizationMembershipResponse]],
)
def get_organization_members(
    organization_id: UUID,
    current_human: CurrentHumanDep,
    session: SessionDep,
    limit: Limit = 100,
) -> dict[str, list[OrganizationMembershipResponse]]:
    try:
        return {
            "items": list_members(
                session,
                user=current_human,
                organization_id=organization_id,
                limit=limit,
            )
        }
    except OrganizationSelfGovernanceNotFoundError as exc:
        raise _not_found() from exc


@router.post(
    "/organizations/{organization_id}/agents/{agent_id}/confirmation",
    response_model=OrganizationAgentConfirmationResponse,
)
def confirm_owned_organization_agent_action(
    organization_id: UUID,
    agent_id: UUID,
    payload: OrganizationAgentConfirmationCreate,
    request: Request,
    current_human: CurrentHumanDep,
    session: SessionDep,
    settings: SettingsDep,
    csrf_guard: HumanCsrfDep,
) -> OrganizationAgentConfirmationResponse:
    del csrf_guard
    try:
        authorize_owned_agent_management(
            session,
            user=current_human,
            organization_id=organization_id,
            agent_id=agent_id,
        )
    except OrganizationSelfGovernanceNotFoundError as exc:
        raise _not_found() from exc
    except OrganizationAccessDeniedError as exc:
        raise _forbidden() from exc
    except OrganizationAgentOwnershipRequiredError as exc:
        raise _agent_management_not_found() from exc
    _verify_password_reauthentication(
        request,
        session,
        settings,
        current_human,
        password=payload.password.get_secret_value(),
    )
    created = create_human_confirmation(
        session,
        settings,
        user=current_human,
        human_session_id=human_session_id_from_request(request),
        intent=f"organization_agent.{payload.intent}",
        target_type="organization_agent",
        target_id=_organization_agent_confirmation_target(organization_id, agent_id),
        request_id=request.state.request_id,
    )
    return OrganizationAgentConfirmationResponse(
        confirmation_token=created.raw_token,
        intent=payload.intent,
        organization_id=organization_id,
        agent_id=agent_id,
        expires_at=created.expires_at,
    )


def _consume_organization_agent_confirmation(
    *,
    organization_id: UUID,
    agent_id: UUID,
    intent: str,
    raw_confirmation: str | None,
    request: Request,
    current_human: CurrentHumanDep,
    session: SessionDep,
    settings: SettingsDep,
) -> None:
    if raw_confirmation is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "human_confirmation_required"},
        )
    try:
        consume_human_confirmation(
            session,
            settings,
            user=current_human,
            human_session_id=human_session_id_from_request(request),
            intent=f"organization_agent.{intent}",
            target_type="organization_agent",
            target_id=_organization_agent_confirmation_target(organization_id, agent_id),
            raw_token=raw_confirmation,
        )
    except HumanConfirmationInvalidError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "human_confirmation_invalid"},
        ) from exc


@router.put(
    "/organizations/{organization_id}/agents/{agent_id}",
    response_model=OrganizationAgentResponse,
)
def assign_my_agent_to_organization(
    organization_id: UUID,
    agent_id: UUID,
    request: Request,
    current_human: CurrentHumanDep,
    session: SessionDep,
    settings: SettingsDep,
    csrf_guard: HumanCsrfDep,
    confirmation: Annotated[str | None, Header(alias=HUMAN_CONFIRMATION_HEADER)] = None,
) -> OrganizationAgentResponse:
    del csrf_guard
    _consume_organization_agent_confirmation(
        organization_id=organization_id,
        agent_id=agent_id,
        intent="assign",
        raw_confirmation=confirmation,
        request=request,
        current_human=current_human,
        session=session,
        settings=settings,
    )
    try:
        return assign_owned_agent(
            session,
            user=current_human,
            organization_id=organization_id,
            agent_id=agent_id,
            human_session_id=human_session_id_from_request(request),
            request_id=request.state.request_id,
        )
    except OrganizationSelfGovernanceNotFoundError as exc:
        raise _not_found() from exc
    except OrganizationAccessDeniedError as exc:
        raise _forbidden() from exc
    except OrganizationAgentOwnershipRequiredError as exc:
        raise _agent_management_not_found() from exc
    except OrganizationAgentAlreadyAssignedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "agent_already_assigned_to_organization"},
        ) from exc


@router.delete(
    "/organizations/{organization_id}/agents/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_my_agent_from_organization(
    organization_id: UUID,
    agent_id: UUID,
    request: Request,
    current_human: CurrentHumanDep,
    session: SessionDep,
    settings: SettingsDep,
    csrf_guard: HumanCsrfDep,
    confirmation: Annotated[str | None, Header(alias=HUMAN_CONFIRMATION_HEADER)] = None,
) -> None:
    del csrf_guard
    _consume_organization_agent_confirmation(
        organization_id=organization_id,
        agent_id=agent_id,
        intent="remove",
        raw_confirmation=confirmation,
        request=request,
        current_human=current_human,
        session=session,
        settings=settings,
    )
    try:
        remove_owned_agent(
            session,
            user=current_human,
            organization_id=organization_id,
            agent_id=agent_id,
            human_session_id=human_session_id_from_request(request),
            request_id=request.state.request_id,
        )
    except OrganizationSelfGovernanceNotFoundError as exc:
        raise _not_found() from exc
    except OrganizationAccessDeniedError as exc:
        raise _forbidden() from exc
    except (
        OrganizationAgentOwnershipRequiredError,
        OrganizationAgentAssignmentNotFoundError,
    ) as exc:
        raise _agent_management_not_found() from exc


@router.post(
    "/organizations/{organization_id}/invitations",
    response_model=OrganizationInvitationCreated,
    status_code=status.HTTP_201_CREATED,
)
def invite_organization_member(
    organization_id: UUID,
    payload: OrganizationInvitationCreate,
    request: Request,
    current_human: CurrentHumanDep,
    session: SessionDep,
    settings: SettingsDep,
    csrf_guard: HumanCsrfDep,
) -> OrganizationInvitationCreated:
    del csrf_guard
    try:
        return create_invitation(
            session,
            settings,
            user=current_human,
            organization_id=organization_id,
            payload=payload,
            human_session_id=human_session_id_from_request(request),
            request_id=request.state.request_id,
        )
    except OrganizationSelfGovernanceNotFoundError as exc:
        raise _not_found() from exc
    except OrganizationAccessDeniedError as exc:
        raise _forbidden() from exc
    except OrganizationAlreadyMemberError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "organization_already_member"},
        ) from exc
    except OrganizationInvitationAlreadyPendingError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "organization_invitation_already_pending"},
        ) from exc
    except EmailDeliveryError as exc:
        session.rollback()
        raise HTTPException(
            status_code=503,
            detail={"code": "email_delivery_unavailable"},
        ) from exc


@router.get(
    "/organizations/{organization_id}/invitations",
    response_model=dict[str, list[OrganizationInvitationResponse]],
)
def get_organization_invitations(
    organization_id: UUID,
    current_human: CurrentHumanDep,
    session: SessionDep,
    limit: Limit = 100,
) -> dict[str, list[OrganizationInvitationResponse]]:
    try:
        return {
            "items": list_invitations(
                session,
                user=current_human,
                organization_id=organization_id,
                limit=limit,
            )
        }
    except OrganizationSelfGovernanceNotFoundError as exc:
        raise _not_found() from exc
    except OrganizationAccessDeniedError as exc:
        raise _forbidden() from exc


@router.post(
    "/organization-invitations/preview",
    response_model=OrganizationInvitationPreview,
)
def preview_organization_invitation(
    payload: OrganizationInvitationAccept,
    current_human: CurrentHumanDep,
    session: SessionDep,
    settings: SettingsDep,
) -> OrganizationInvitationPreview:
    try:
        return preview_invitation(
            session,
            settings,
            user=current_human,
            raw_token=payload.token,
        )
    except OrganizationInvitationInvalidError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "organization_invitation_invalid"},
        ) from exc
    except OrganizationAlreadyMemberError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "organization_already_member"},
        ) from exc


@router.post(
    "/organization-invitations/accept",
    response_model=OrganizationInvitationAccepted,
)
def accept_organization_invitation(
    payload: OrganizationInvitationAccept,
    request: Request,
    current_human: CurrentHumanDep,
    session: SessionDep,
    settings: SettingsDep,
    csrf_guard: HumanCsrfDep,
) -> OrganizationInvitationAccepted:
    del csrf_guard
    try:
        return accept_invitation(
            session,
            settings,
            user=current_human,
            raw_token=payload.token,
            human_session_id=human_session_id_from_request(request),
            request_id=request.state.request_id,
        )
    except OrganizationInvitationInvalidError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "organization_invitation_invalid"},
        ) from exc
    except OrganizationAlreadyMemberError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "organization_already_member"},
        ) from exc


@router.delete(
    "/organizations/{organization_id}/invitations/{invitation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_organization_invitation(
    organization_id: UUID,
    invitation_id: UUID,
    request: Request,
    current_human: CurrentHumanDep,
    session: SessionDep,
    csrf_guard: HumanCsrfDep,
) -> None:
    del csrf_guard
    try:
        revoke_invitation(
            session,
            user=current_human,
            organization_id=organization_id,
            invitation_id=invitation_id,
            human_session_id=human_session_id_from_request(request),
            request_id=request.state.request_id,
        )
    except OrganizationSelfGovernanceNotFoundError as exc:
        raise _not_found() from exc
    except OrganizationAccessDeniedError as exc:
        raise _forbidden() from exc


@router.patch(
    "/organizations/{organization_id}/members/{human_user_id}",
    response_model=OrganizationMembershipResponse,
)
def update_organization_member(
    organization_id: UUID,
    human_user_id: UUID,
    payload: OrganizationMembershipUpdate,
    request: Request,
    current_human: CurrentHumanDep,
    session: SessionDep,
    csrf_guard: HumanCsrfDep,
) -> OrganizationMembershipResponse:
    del csrf_guard
    try:
        return change_member_role(
            session,
            actor=current_human,
            organization_id=organization_id,
            member_user_id=human_user_id,
            role=payload.role,
            human_session_id=human_session_id_from_request(request),
            request_id=request.state.request_id,
        )
    except OrganizationSelfGovernanceNotFoundError as exc:
        raise _not_found() from exc
    except OrganizationAccessDeniedError as exc:
        raise _forbidden() from exc
    except LastOrganizationOwnerError as exc:
        raise HTTPException(status_code=409, detail={"code": "last_organization_owner"}) from exc


@router.delete(
    "/organizations/{organization_id}/members/{human_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_organization_member(
    organization_id: UUID,
    human_user_id: UUID,
    request: Request,
    current_human: CurrentHumanDep,
    session: SessionDep,
    csrf_guard: HumanCsrfDep,
) -> None:
    del csrf_guard
    try:
        remove_member(
            session,
            actor=current_human,
            organization_id=organization_id,
            member_user_id=human_user_id,
            human_session_id=human_session_id_from_request(request),
            request_id=request.state.request_id,
        )
    except OrganizationSelfGovernanceNotFoundError as exc:
        raise _not_found() from exc
    except OrganizationAccessDeniedError as exc:
        raise _forbidden() from exc
    except LastOrganizationOwnerError as exc:
        raise HTTPException(status_code=409, detail={"code": "last_organization_owner"}) from exc


@router.delete(
    "/organizations/{organization_id}/membership",
    status_code=status.HTTP_204_NO_CONTENT,
)
def leave_organization(
    organization_id: UUID,
    request: Request,
    current_human: CurrentHumanDep,
    session: SessionDep,
    csrf_guard: HumanCsrfDep,
) -> None:
    del csrf_guard
    try:
        remove_member(
            session,
            actor=current_human,
            organization_id=organization_id,
            member_user_id=current_human.id,
            human_session_id=human_session_id_from_request(request),
            request_id=request.state.request_id,
            self_exit=True,
        )
    except OrganizationSelfGovernanceNotFoundError as exc:
        raise _not_found() from exc
    except LastOrganizationOwnerError as exc:
        raise HTTPException(status_code=409, detail={"code": "last_organization_owner"}) from exc


@router.post(
    "/organizations/{organization_id}/domains",
    response_model=OrganizationDomainCreated,
    status_code=status.HTTP_201_CREATED,
)
def add_organization_domain(
    organization_id: UUID,
    payload: OrganizationDomainCreate,
    request: Request,
    current_human: CurrentHumanDep,
    session: SessionDep,
    settings: SettingsDep,
    csrf_guard: HumanCsrfDep,
) -> OrganizationDomainCreated:
    del csrf_guard
    try:
        return create_domain_claim(
            session,
            settings,
            user=current_human,
            organization_id=organization_id,
            payload=payload,
            human_session_id=human_session_id_from_request(request),
            request_id=request.state.request_id,
        )
    except OrganizationSelfGovernanceNotFoundError as exc:
        raise _not_found() from exc
    except OrganizationAccessDeniedError as exc:
        raise _forbidden() from exc
    except OrganizationDomainConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "organization_domain_conflict"},
        ) from exc


@router.get(
    "/organizations/{organization_id}/domains",
    response_model=dict[str, list[OrganizationDomainResponse]],
)
def get_organization_domains(
    organization_id: UUID,
    current_human: CurrentHumanDep,
    session: SessionDep,
) -> dict[str, list[OrganizationDomainResponse]]:
    try:
        return {
            "items": list_domains(
                session,
                user=current_human,
                organization_id=organization_id,
            )
        }
    except OrganizationSelfGovernanceNotFoundError as exc:
        raise _not_found() from exc


@router.post(
    "/organizations/{organization_id}/domains/{domain_id}/verify",
    response_model=OrganizationDomainResponse,
)
def verify_organization_domain(
    organization_id: UUID,
    domain_id: UUID,
    request: Request,
    current_human: CurrentHumanDep,
    session: SessionDep,
    settings: SettingsDep,
    csrf_guard: HumanCsrfDep,
) -> OrganizationDomainResponse:
    del csrf_guard
    try:
        return verify_domain_claim(
            session,
            settings,
            user=current_human,
            organization_id=organization_id,
            domain_id=domain_id,
            human_session_id=human_session_id_from_request(request),
            request_id=request.state.request_id,
        )
    except OrganizationSelfGovernanceNotFoundError as exc:
        raise _not_found() from exc
    except OrganizationAccessDeniedError as exc:
        raise _forbidden() from exc
    except OrganizationDomainNotVerifiedError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "organization_domain_not_verified"},
        ) from exc
    except OrganizationDomainLookupError as exc:
        session.rollback()
        raise HTTPException(
            status_code=503,
            detail={"code": "organization_domain_lookup_unavailable"},
        ) from exc


@router.delete(
    "/organizations/{organization_id}/domains/{domain_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_organization_domain(
    organization_id: UUID,
    domain_id: UUID,
    request: Request,
    current_human: CurrentHumanDep,
    session: SessionDep,
    csrf_guard: HumanCsrfDep,
) -> None:
    del csrf_guard
    try:
        revoke_domain_claim(
            session,
            user=current_human,
            organization_id=organization_id,
            domain_id=domain_id,
            human_session_id=human_session_id_from_request(request),
            request_id=request.state.request_id,
        )
    except OrganizationSelfGovernanceNotFoundError as exc:
        raise _not_found() from exc
    except OrganizationAccessDeniedError as exc:
        raise _forbidden() from exc
