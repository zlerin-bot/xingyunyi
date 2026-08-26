from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status

from agentpost.accounts.mailer import EmailDeliveryError
from agentpost.api.dependencies import SessionDep, SettingsDep
from agentpost.control.auth import CurrentHumanDep
from agentpost.control.human_security import HumanCsrfDep, human_session_id_from_request
from agentpost.control.schemas import OrganizationCreate, OrganizationMembershipResponse
from agentpost.organizations.schemas import (
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
    OrganizationAlreadyMemberError,
    OrganizationDomainConflictError,
    OrganizationDomainLookupError,
    OrganizationDomainNotVerifiedError,
    OrganizationInvitationAlreadyPendingError,
    OrganizationInvitationInvalidError,
    OrganizationSelfGovernanceNotFoundError,
    OrganizationSlugConflictError,
    accept_invitation,
    change_member_role,
    create_domain_claim,
    create_invitation,
    create_owned_organization,
    list_domains,
    list_invitations,
    list_members,
    preview_invitation,
    remove_member,
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
