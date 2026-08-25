from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event
from typing import Protocol

import httpx

from agentpost_sdk.errors import AuthenticationError, ConfigurationError
from agentpost_sdk.models import Message
from agentpost_sdk.onboarding import PairingInstructions


@dataclass(frozen=True)
class ConnectorCredential:
    server: str
    profile: str
    connector_id: str
    agent_address: str
    api_key: str = field(repr=False)


class CredentialStore(Protocol):
    def load(self, *, server: str, profile: str) -> ConnectorCredential | None: ...

    def save(self, credential: ConnectorCredential) -> None: ...

    def delete(self, *, server: str, profile: str) -> None: ...


class CursorStore(Protocol):
    def load(self) -> str | None: ...

    def save(self, cursor: str) -> None: ...


class KeyringCredentialStore:
    """Store Connector credentials in the operating-system credential vault."""

    def __init__(self, *, service_name: str = "me.agentpost.connector", backend=None) -> None:
        if not service_name or len(service_name) > 200:
            raise ConfigurationError("keyring service_name must contain 1-200 characters")
        if backend is None:
            try:
                import keyring as backend
            except ImportError as exc:
                raise ConfigurationError(
                    "OS credential storage requires the agentpost[connector] extra"
                ) from exc
        self._service_name = service_name
        self._backend = backend

    @staticmethod
    def _account(server: str, profile: str) -> str:
        return hashlib.sha256(f"{server}\0{profile}".encode()).hexdigest()

    def load(self, *, server: str, profile: str) -> ConnectorCredential | None:
        try:
            raw = self._backend.get_password(
                self._service_name,
                self._account(server, profile),
            )
        except Exception as exc:
            raise ConfigurationError("OS credential storage is unavailable") from exc
        if raw is None:
            return None
        try:
            payload = json.loads(raw)
            credential = ConnectorCredential(
                server=str(payload["server"]),
                profile=str(payload["profile"]),
                connector_id=str(payload["connector_id"]),
                agent_address=str(payload["agent_address"]),
                api_key=str(payload["api_key"]),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ConfigurationError("Stored Connector credential is malformed") from exc
        if credential.server != server or credential.profile != profile:
            raise ConfigurationError("Stored Connector credential does not match this profile")
        if not credential.api_key.startswith("agt_"):
            raise ConfigurationError("Stored Connector credential is malformed")
        return credential

    def save(self, credential: ConnectorCredential) -> None:
        payload = json.dumps(
            {
                "server": credential.server,
                "profile": credential.profile,
                "connector_id": credential.connector_id,
                "agent_address": credential.agent_address,
                "api_key": credential.api_key,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        try:
            self._backend.set_password(
                self._service_name,
                self._account(credential.server, credential.profile),
                payload,
            )
        except Exception as exc:
            raise ConfigurationError("OS credential storage is unavailable") from exc

    def delete(self, *, server: str, profile: str) -> None:
        try:
            self._backend.delete_password(
                self._service_name,
                self._account(server, profile),
            )
        except Exception:
            # Missing entries and platform-specific delete failures must not expose secrets.
            return


class JsonCursorStore:
    """Persist only an opaque inbox cursor; this file never contains credentials or messages."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)

    def load(self) -> str | None:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, ValueError) as exc:
            raise ConfigurationError("Connector cursor state is unreadable") from exc
        cursor = payload.get("cursor") if isinstance(payload, dict) else None
        if cursor is None:
            return None
        if not isinstance(cursor, str) or not cursor or len(cursor) > 4096:
            raise ConfigurationError("Connector cursor state is malformed")
        return cursor

    def save(self, cursor: str) -> None:
        if not cursor or len(cursor) > 4096:
            raise ConfigurationError("Connector cursor must contain 1-4096 characters")
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.{secrets.token_hex(8)}.tmp")
        try:
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump({"cursor": cursor}, stream, separators=(",", ":"))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)


class MemoryCursorStore:
    def __init__(self) -> None:
        self.cursor: str | None = None

    def load(self) -> str | None:
        return self.cursor

    def save(self, cursor: str) -> None:
        self.cursor = cursor


class ManagedConnector:
    def __init__(
        self,
        *,
        client,
        profile: str,
        credential_store: CredentialStore,
    ) -> None:
        self.client = client
        self.profile = profile
        self.credential_store = credential_store

    def __enter__(self) -> ManagedConnector:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self.client.close()

    def heartbeat(self, *, health_status: str = "healthy", last_error_code: str | None = None):
        return self.client.connector.heartbeat(
            health_status=health_status,
            last_error_code=last_error_code,
        )

    def rotate_credential(self):
        rotation = self.client.connector.rotate_credential()
        self.credential_store.save(
            ConnectorCredential(
                server=self.client.server,
                profile=self.profile,
                connector_id=rotation.connector_id,
                agent_address=rotation.agent.address,
                api_key=rotation.api_key.get_secret_value(),
            )
        )
        return rotation

    def forget(self) -> None:
        self.credential_store.delete(server=self.client.server, profile=self.profile)


def connect_managed(
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
    from agentpost_sdk.client import AgentPost, _clean_server

    cleaned_server = _clean_server(server)
    stable_profile = (profile or f"{connector_type}:{device_name or display_name}").strip()
    if not stable_profile or len(stable_profile) > 200:
        raise ConfigurationError("Connector profile must contain 1-200 characters")
    store = credential_store or KeyringCredentialStore()
    stored = store.load(server=cleaned_server, profile=stable_profile)
    if stored is not None:
        client = AgentPost(cleaned_server, stored.api_key, timeout=timeout, transport=transport)
        client._connector_id = stored.connector_id
        client._agent_address = stored.agent_address
        try:
            client.connector.heartbeat()
            return ManagedConnector(
                client=client,
                profile=stable_profile,
                credential_store=store,
            )
        except AuthenticationError:
            client.close()
            store.delete(server=cleaned_server, profile=stable_profile)

    client = AgentPost.connect(
        cleaned_server,
        connector_type=connector_type,
        display_name=display_name,
        device_name=device_name,
        client_version=client_version,
        capabilities=capabilities,
        requested_existing_agent_id=requested_existing_agent_id,
        open_browser=open_browser,
        on_pairing=on_pairing,
        timeout=timeout,
        pairing_timeout=pairing_timeout,
        sleeper=sleeper,
        transport=transport,
    )
    if not client._connector_id or not client._agent_address:
        client.close()
        raise ConfigurationError("Pairing approval did not identify the Connector")
    store.save(
        ConnectorCredential(
            server=cleaned_server,
            profile=stable_profile,
            connector_id=client._connector_id,
            agent_address=client._agent_address,
            api_key=client._api_key,
        )
    )
    return ManagedConnector(client=client, profile=stable_profile, credential_store=store)


class ConnectorWorker:
    """Durable single-consumer polling worker for one current Connector.

    Message bodies are untrusted external input. The handler must be idempotent by
    message_id because transport recovery may deliberately replay a message.
    """

    def __init__(
        self,
        connector: ManagedConnector,
        *,
        handler: Callable[[Message], None],
        cursor_store: CursorStore,
    ) -> None:
        self.connector = connector
        self.handler = handler
        self.cursor_store = cursor_store

    def run_once(self, *, max_messages: int = 50) -> int:
        if not 1 <= max_messages <= 100:
            raise ConfigurationError("max_messages must be between 1 and 100")
        processed = 0
        cursor = self.cursor_store.load()
        self.connector.heartbeat()
        while processed < max_messages:
            page = self.connector.client.inbox.list(limit=1, cursor=cursor)
            if not page.items:
                break
            message = page.items[0]
            try:
                if message.delivery.status == "delivered":
                    message = message.read()
                self.handler(message)
                if message.delivery.status != "acked":
                    message.ack()
            except Exception:
                try:
                    self.connector.heartbeat(
                        health_status="degraded",
                        last_error_code="MESSAGE_HANDLER_ERROR",
                    )
                except Exception:
                    pass
                raise
            if page.next_cursor:
                cursor = page.next_cursor
                self.cursor_store.save(cursor)
            processed += 1
            if not page.has_more:
                break
        self.connector.heartbeat()
        return processed

    def run_forever(
        self,
        *,
        stop_event: Event,
        poll_interval_seconds: float = 30.0,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if poll_interval_seconds <= 0:
            raise ConfigurationError("poll_interval_seconds must be positive")
        backoff = 1.0
        while not stop_event.is_set():
            try:
                self.run_once()
                backoff = 1.0
                delay = poll_interval_seconds
            except AuthenticationError:
                self.connector.forget()
                raise
            except Exception:
                delay = min(60.0, backoff)
                backoff = min(60.0, backoff * 2)
            if sleeper is time.sleep:
                if stop_event.wait(delay):
                    return
            else:
                sleeper(delay)
