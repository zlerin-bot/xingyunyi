from __future__ import annotations

import hashlib
import os
import secrets
import time
import webbrowser
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO
from urllib.parse import urlparse
from uuid import UUID

import httpx
from pydantic import ValidationError as PydanticValidationError

from agentpost_sdk.errors import (
    ConfigurationError,
    ProtocolError,
    ResponseError,
    TransportError,
    error_for_status,
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
    RecipientResolution,
)

if TYPE_CHECKING:
    from agentpost_sdk.connector import CredentialStore, ManagedConnector
    from agentpost_sdk.onboarding import PairingInstructions, PairingSession

_BODY_FORMATS = {"text", "markdown", "json"}


def _idempotency_key() -> str:
    return f"sdk_{secrets.token_urlsafe(24)}"


def _clean_server(value: str) -> str:
    server = value.strip().rstrip("/")
    parsed = urlparse(server)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ConfigurationError("server must be an absolute HTTP(S) URL")
    if parsed.query or parsed.fragment:
        raise ConfigurationError("server must not contain a query or fragment")
    return server


class _MessagesResource:
    def __init__(self, owner: AgentPost) -> None:
        self._owner = owner

    def get(self, message_id: str) -> Message:
        return self._owner._message(self._owner._request("GET", f"/messages/{message_id}"))

    def read(self, message_id: str) -> Message:
        return self._owner._message(self._owner._request("POST", f"/messages/{message_id}/read"))

    def ack(self, message_id: str) -> Message:
        return self._owner._message(self._owner._request("POST", f"/messages/{message_id}/ack"))

    def reply(
        self,
        message_id: str,
        body: Any,
        *,
        subject: str = "",
        type: str = "message",
        format: str = "text",
        task: Mapping[str, Any] | None = None,
        result: Mapping[str, Any] | None = None,
        attachments: list[UUID | str] | None = None,
        priority: str = "normal",
        requires_ack: bool = True,
        metadata: Mapping[str, Any] | None = None,
        expires_at: str | None = None,
        idempotency_key: str | None = None,
    ) -> Message:
        if format not in _BODY_FORMATS:
            raise ConfigurationError("format must be text, markdown, or json")
        if type != "task" and task is not None:
            raise ConfigurationError("task payload is only valid for task messages")
        if type == "result" and result is None:
            raise ConfigurationError("result replies require a result payload")
        if type != "result" and result is not None:
            raise ConfigurationError("result payload is only valid for result replies")
        idem = idempotency_key or _idempotency_key()
        payload: dict[str, Any] = {
            "type": type,
            "subject": subject,
            "content": {"format": format, "body": body},
            "attachments": [str(item) for item in attachments or []],
            "priority": priority,
            "requires_ack": requires_ack,
            "metadata": dict(metadata or {}),
            "expires_at": expires_at,
        }
        if type == "task" and task is None:
            if not isinstance(body, str) or not body:
                raise ConfigurationError("task messages require a non-empty string body")
            task = {"instruction": body}
        if task is not None:
            payload["task"] = dict(task)
        if result is not None:
            payload["result"] = dict(result)
        data, replayed = self._owner._idempotent_request(
            "POST",
            f"/messages/{message_id}/reply",
            json=payload,
            idempotency_key=idem,
        )
        return self._owner._message(data, idempotency_replayed=replayed)


class _InboxResource:
    def __init__(self, owner: AgentPost) -> None:
        self._owner = owner

    def list(
        self,
        *,
        status: str | None = None,
        sender: str | None = None,
        type: str | None = None,
        priority: str | None = None,
        since: str | datetime | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> InboxPage:
        params = {
            key: value
            for key, value in {
                "status": status,
                "sender": sender,
                "type": type,
                "priority": priority,
                "since": since.isoformat() if hasattr(since, "isoformat") else since,
                "limit": limit,
                "cursor": cursor,
            }.items()
            if value is not None
        }
        data = self._owner._request("GET", "/inbox", params=params)
        try:
            page = InboxPage.model_validate(data)
        except PydanticValidationError as exc:
            raise self._owner._protocol_error("Malformed inbox response", exc) from exc
        page.items = [item._bind(self._owner) for item in page.items]
        return page

    def unread(self, **kwargs: Any) -> InboxPage:
        kwargs["status"] = "unread"
        return self.list(**kwargs)


class _AttachmentsResource:
    def __init__(self, owner: AgentPost) -> None:
        self._owner = owner

    def upload(
        self,
        source: str | os.PathLike[str] | BinaryIO,
        *,
        filename: str | None = None,
        content_type: str = "application/octet-stream",
    ) -> Attachment:
        @contextmanager
        def opened() -> Iterator[tuple[BinaryIO, str]]:
            if isinstance(source, (str, os.PathLike)):
                path = Path(source)
                with path.open("rb") as stream:
                    yield stream, filename or path.name
            else:
                inferred = filename or Path(str(getattr(source, "name", "attachment.bin"))).name
                yield source, inferred

        with opened() as (stream, upload_name):
            data = self._owner._request(
                "POST",
                "/attachments",
                files={"file": (upload_name, stream, content_type)},
            )
        try:
            return Attachment.model_validate(data)
        except PydanticValidationError as exc:
            raise self._owner._protocol_error("Malformed attachment response", exc) from exc

    def download(
        self,
        attachment_id: UUID | str,
        destination: str | os.PathLike[str],
        *,
        expected_sha256: str | None = None,
        sha256: str | None = None,
    ) -> DownloadedFile:
        if expected_sha256 is not None and sha256 is not None:
            raise ConfigurationError("use expected_sha256 or sha256, not both")
        expected_digest = expected_sha256 or sha256
        target = Path(destination)
        if target.exists() and target.is_dir():
            raise ConfigurationError("destination must be a file path, not a directory")
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(f".{target.name}.{secrets.token_hex(8)}.part")
        digest = hashlib.sha256()
        size = 0
        try:
            with self._owner._stream("GET", f"/attachments/{attachment_id}") as response:
                with partial.open("xb") as sink:
                    for chunk in response.iter_bytes():
                        sink.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
                    sink.flush()
                    os.fsync(sink.fileno())
            actual_sha = digest.hexdigest()
            if expected_digest is not None and not secrets.compare_digest(
                actual_sha, expected_digest.lower()
            ):
                raise ProtocolError(
                    "Downloaded attachment SHA-256 does not match",
                    status_code=200,
                    code="ATTACHMENT_DIGEST_MISMATCH",
                )
            os.replace(partial, target)
            return DownloadedFile(path=target, size=size, sha256=actual_sha)
        except Exception:
            partial.unlink(missing_ok=True)
            raise


class _ApprovalsResource:
    def __init__(self, owner: AgentPost) -> None:
        self._owner = owner

    def create(
        self,
        action_type: str,
        summary: str,
        *,
        justification: str | None = None,
        risk_level: str = "medium",
        payload: Mapping[str, Any] | None = None,
        expires_at: str | None = None,
        idempotency_key: str | None = None,
    ) -> ApprovalRequest:
        idem = idempotency_key or _idempotency_key()
        data, replayed = self._owner._idempotent_request(
            "POST",
            "/approval-requests",
            json={
                "action_type": action_type,
                "summary": summary,
                "justification": justification,
                "risk_level": risk_level,
                "payload": dict(payload or {}),
                "expires_at": expires_at,
            },
            idempotency_key=idem,
        )
        return self._owner._approval(data, idempotency_replayed=replayed)

    def list(self, *, status: str | None = None, limit: int = 50) -> ApprovalPage:
        params = {"limit": limit}
        if status is not None:
            params["status"] = status
        data = self._owner._request("GET", "/approval-requests", params=params)
        try:
            return ApprovalPage.model_validate(data)
        except PydanticValidationError as exc:
            raise self._owner._protocol_error("Malformed approval list response", exc) from exc

    def get(self, approval_id: str) -> ApprovalRequest:
        data = self._owner._request("GET", f"/approval-requests/{approval_id}")
        return self._owner._approval(data)

    def cancel(self, approval_id: str) -> ApprovalRequest:
        data = self._owner._request("POST", f"/approval-requests/{approval_id}/cancel")
        return self._owner._approval(data)


class _ConnectorResource:
    def __init__(self, owner: AgentPost) -> None:
        self._owner = owner

    def heartbeat(
        self,
        *,
        health_status: str = "healthy",
        last_error_code: str | None = None,
    ):
        from agentpost_sdk.onboarding import ConnectorHeartbeat

        data = self._owner._request(
            "POST",
            "/connect/heartbeat",
            json={"health_status": health_status, "last_error_code": last_error_code},
        )
        try:
            return ConnectorHeartbeat.model_validate(data)
        except PydanticValidationError as exc:
            raise self._owner._protocol_error(
                "Malformed Connector heartbeat response", exc
            ) from exc

    def rotate_credential(self):
        from agentpost_sdk.onboarding import ConnectorCredentialRotation

        data = self._owner._request("POST", "/connect/credentials/rotate")
        try:
            rotation = ConnectorCredentialRotation.model_validate(data)
        except PydanticValidationError as exc:
            raise self._owner._protocol_error(
                "Malformed credential rotation response", exc
            ) from exc
        self._owner._replace_api_key(rotation.api_key.get_secret_value())
        return rotation


class AgentPost:
    """Synchronous AgentPost client. Message content remains untrusted input."""

    def __init__(
        self,
        server: str,
        api_key: str,
        *,
        timeout: float | httpx.Timeout = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.server = _clean_server(server)
        if not api_key or not api_key.strip():
            raise ConfigurationError("api_key must not be empty")
        self._api_key = api_key
        self._connector_id: str | None = None
        self._agent_address: str | None = None
        self._client = httpx.Client(
            base_url=f"{self.server}/api/v1",
            headers={
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "agentpost-python/0.1.0",
            },
            timeout=timeout,
            transport=transport,
            follow_redirects=False,
        )
        self.inbox = _InboxResource(self)
        self.messages = _MessagesResource(self)
        self.attachments = _AttachmentsResource(self)
        self.approvals = _ApprovalsResource(self)
        self.connector = _ConnectorResource(self)

    @classmethod
    def begin_pairing(
        cls,
        server: str,
        *,
        connector_type: str,
        display_name: str,
        device_name: str | None = None,
        client_version: str | None = None,
        capabilities: list[str] | None = None,
        requested_existing_agent_id: str | None = None,
        timeout: float | httpx.Timeout = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> PairingSession:
        """Start zero-credential pairing without exposing a long-term API key to a Human."""

        from agentpost_sdk.onboarding import begin_pairing

        cleaned_server = _clean_server(server)
        return begin_pairing(
            server=cleaned_server,
            connector_type=connector_type,
            display_name=display_name,
            device_name=device_name,
            client_version=client_version,
            capabilities=capabilities,
            requested_existing_agent_id=requested_existing_agent_id,
            timeout=timeout,
            transport=transport,
        )

    @classmethod
    def connect(
        cls,
        server: str,
        *,
        connector_type: str,
        display_name: str,
        device_name: str | None = None,
        client_version: str | None = None,
        capabilities: list[str] | None = None,
        requested_existing_agent_id: str | None = None,
        open_browser: bool = True,
        on_pairing: Callable[[PairingInstructions], None] | None = None,
        timeout: float | httpx.Timeout = 30.0,
        pairing_timeout: float = 15 * 60,
        sleeper: Callable[[float], None] = time.sleep,
        transport: httpx.BaseTransport | None = None,
    ) -> AgentPost:
        """Pair, wait for Human authorization, and return an authenticated client."""

        pairing = cls.begin_pairing(
            server,
            connector_type=connector_type,
            display_name=display_name,
            device_name=device_name,
            client_version=client_version,
            capabilities=capabilities,
            requested_existing_agent_id=requested_existing_agent_id,
            timeout=timeout,
            transport=transport,
        )
        try:
            if on_pairing is not None:
                on_pairing(pairing.instructions)
            if open_browser:
                webbrowser.open(pairing.instructions.verification_uri_complete)
            return pairing.wait(timeout=pairing_timeout, sleeper=sleeper)
        except Exception:
            pairing.close()
            raise

    @classmethod
    def connect_managed(
        cls,
        server: str,
        *,
        connector_type: str,
        display_name: str,
        profile: str | None = None,
        device_name: str | None = None,
        client_version: str | None = None,
        capabilities: list[str] | None = None,
        requested_existing_agent_id: str | None = None,
        credential_store: CredentialStore | None = None,
        open_browser: bool = True,
        on_pairing: Callable[[PairingInstructions], None] | None = None,
        timeout: float | httpx.Timeout = 30.0,
        pairing_timeout: float = 15 * 60,
        sleeper: Callable[[float], None] = time.sleep,
        transport: httpx.BaseTransport | None = None,
    ) -> ManagedConnector:
        """Restore from the OS vault or perform Human-authorized pairing once."""

        from agentpost_sdk.connector import connect_managed

        return connect_managed(
            server,
            connector_type=connector_type,
            display_name=display_name,
            profile=profile,
            device_name=device_name,
            client_version=client_version,
            capabilities=capabilities,
            requested_existing_agent_id=requested_existing_agent_id,
            credential_store=credential_store,
            open_browser=open_browser,
            on_pairing=on_pairing,
            timeout=timeout,
            pairing_timeout=pairing_timeout,
            sleeper=sleeper,
            transport=transport,
        )

    def __repr__(self) -> str:
        return f"AgentPost(server={self.server!r})"

    def __enter__(self) -> AgentPost:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _replace_api_key(self, api_key: str) -> None:
        self._api_key = api_key
        self._client.headers["Authorization"] = f"Bearer {api_key}"

    def send(
        self,
        to: str,
        subject: str,
        body: Any,
        *,
        type: str = "message",
        format: str = "text",
        task: Mapping[str, Any] | None = None,
        attachments: list[UUID | str] | None = None,
        priority: str = "normal",
        requires_ack: bool = True,
        metadata: Mapping[str, Any] | None = None,
        expires_at: str | None = None,
        idempotency_key: str | None = None,
    ) -> Message:
        """Send once; callers explicitly retry transport failures with the same key."""
        if type == "result":
            raise ConfigurationError("result messages must be created as replies")
        if type != "task" and task is not None:
            raise ConfigurationError("task payload is only valid for task messages")
        if format not in _BODY_FORMATS:
            raise ConfigurationError("format must be text, markdown, or json")
        idem = idempotency_key or _idempotency_key()
        payload: dict[str, Any] = {
            "to": [{"address": to}],
            "type": type,
            "subject": subject,
            "content": {"format": format, "body": body},
            "attachments": [str(item) for item in attachments or []],
            "priority": priority,
            "requires_ack": requires_ack,
            "metadata": dict(metadata or {}),
            "expires_at": expires_at,
        }
        if type == "task" and task is None:
            if not isinstance(body, str) or not body:
                raise ConfigurationError("task messages require a non-empty string body")
            task = {"instruction": body}
        if task is not None:
            payload["task"] = dict(task)
        data, replayed = self._idempotent_request(
            "POST", "/messages", json=payload, idempotency_key=idem
        )
        return self._message(data, idempotency_replayed=replayed)

    def search_agents(
        self,
        *,
        q: str | None = None,
        capability: str | None = None,
        limit: int = 20,
    ) -> list[AgentProfile]:
        if q is None and capability is None:
            raise ConfigurationError("at least one of q or capability must be provided")
        params = {
            key: value
            for key, value in {"q": q, "capability": capability, "limit": limit}.items()
            if value is not None
        }
        data = self._request("GET", "/directory/search", params=params)
        try:
            return DirectoryPage.model_validate(data).items
        except PydanticValidationError as exc:
            raise self._protocol_error("Malformed directory response", exc) from exc

    def resolve_recipient(self, query: str) -> RecipientResolution:
        if not isinstance(query, str) or not query.strip():
            raise ConfigurationError("recipient query must not be blank")
        data = self._request(
            "POST",
            "/directory/resolve",
            json={"query": query},
        )
        try:
            return RecipientResolution.model_validate(data)
        except PydanticValidationError as exc:
            raise self._protocol_error("Malformed recipient resolution response", exc) from exc

    def _message(self, data: Any, *, idempotency_replayed: bool = False) -> Message:
        try:
            message = Message.model_validate(data)
            message.idempotency_replayed = idempotency_replayed
            return message._bind(self)
        except PydanticValidationError as exc:
            raise self._protocol_error("Malformed message response", exc) from exc

    def _approval(
        self,
        data: Any,
        *,
        idempotency_replayed: bool = False,
    ) -> ApprovalRequest:
        try:
            approval = ApprovalRequest.model_validate(data)
            approval.idempotency_replayed = idempotency_replayed
            return approval
        except PydanticValidationError as exc:
            raise self._protocol_error("Malformed approval response", exc) from exc

    def _protocol_error(self, message: str, exc: Exception) -> ProtocolError:
        return ProtocolError(
            message,
            status_code=None,
            code="MALFORMED_RESPONSE",
            details={"validation_error": str(exc)},
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        idempotency_key: str | None = None,
        **kwargs: Any,
    ) -> Any:
        if idempotency_key is not None:
            headers = dict(kwargs.pop("headers", {}))
            headers["Idempotency-Key"] = idempotency_key
            kwargs["headers"] = headers
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise TransportError(
                "AgentPost request did not complete",
                idempotency_key=idempotency_key,
            ) from exc
        if response.is_error:
            self._raise_api_error(response, idempotency_key=idempotency_key)
        if response.status_code == 204:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise ProtocolError(
                "AgentPost returned a non-JSON success response",
                status_code=response.status_code,
                code="MALFORMED_RESPONSE",
                request_id=response.headers.get("X-Request-ID"),
                idempotency_key=idempotency_key,
            ) from exc

    def _idempotent_request(
        self,
        method: str,
        path: str,
        *,
        idempotency_key: str,
        **kwargs: Any,
    ) -> tuple[Any, bool]:
        headers = dict(kwargs.pop("headers", {}))
        headers["Idempotency-Key"] = idempotency_key
        kwargs["headers"] = headers
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise TransportError(
                "AgentPost request did not complete",
                idempotency_key=idempotency_key,
            ) from exc
        if response.is_error:
            self._raise_api_error(response, idempotency_key=idempotency_key)
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProtocolError(
                "AgentPost returned a non-JSON success response",
                status_code=response.status_code,
                code="MALFORMED_RESPONSE",
                request_id=response.headers.get("X-Request-ID"),
                idempotency_key=idempotency_key,
            ) from exc
        replayed = response.headers.get("Idempotency-Replayed", "").casefold() == "true"
        return payload, replayed

    @contextmanager
    def _stream(self, method: str, path: str) -> Iterator[httpx.Response]:
        try:
            with self._client.stream(method, path) as response:
                if response.is_error:
                    response.read()
                    self._raise_api_error(response)
                yield response
        except ResponseError:
            raise
        except httpx.HTTPError as exc:
            raise TransportError("AgentPost stream did not complete") from exc

    @staticmethod
    def _raise_api_error(
        response: httpx.Response,
        *,
        idempotency_key: str | None = None,
    ) -> None:
        request_id = response.headers.get("X-Request-ID")
        try:
            payload = response.json()
        except ValueError:
            payload = None
        error = payload.get("error") if isinstance(payload, dict) else None
        if not isinstance(error, dict):
            raise ProtocolError(
                "AgentPost returned a malformed error response",
                status_code=response.status_code,
                code="MALFORMED_ERROR_RESPONSE",
                request_id=request_id,
                idempotency_key=idempotency_key,
            )
        code = str(error.get("code") or "UNKNOWN_ERROR")
        message = str(error.get("message") or "AgentPost request failed")
        exception_type = error_for_status(response.status_code)
        raise exception_type(
            message,
            status_code=response.status_code,
            code=code,
            request_id=str(error.get("request_id") or request_id or "") or None,
            details=error.get("details", {}),
            idempotency_key=idempotency_key,
        )
