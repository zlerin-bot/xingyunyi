"""Human-friendly entry point for pairing and testing a local AgentPost Connector."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import mimetypes
import os
import platform
import sys
import time
from pathlib import Path
from threading import Event
from typing import Any

from agentpost_sdk import __version__
from agentpost_sdk.client import AgentPost
from agentpost_sdk.codex_setup import CodexSetupResult, configure_codex_mcp
from agentpost_sdk.connector import (
    ConnectorWorker,
    JsonCursorStore,
    KeyringCredentialStore,
    ManagedConnector,
)
from agentpost_sdk.doubao_work_setup import (
    DoubaoWorkSetupResult,
    configure_doubao_work_mcp,
)
from agentpost_sdk.errors import AgentPostError, ConfigurationError, ResponseError
from agentpost_sdk.hermes_setup import (
    HermesSetupResult,
    configure_hermes_mcp,
    preflight_hermes_mcp,
)
from agentpost_sdk.manus_setup import ManusSetupResult, configure_manus_mcp
from agentpost_sdk.models import Message
from agentpost_sdk.onboarding import PairingInstructions
from agentpost_sdk.openclaw_setup import (
    OpenClawSetupResult,
    configure_openclaw_mcp,
    preflight_openclaw_mcp,
)
from agentpost_sdk.workbuddy_setup import WorkBuddySetupResult, configure_workbuddy_mcp

DEFAULT_SERVER = "https://agentpost.me"
MESSAGE_TYPES = (
    "message",
    "task",
    "request",
    "response",
    "notification",
    "event",
    "error",
    "system",
)
REPLY_TYPES = (*MESSAGE_TYPES, "result")


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentpost-connect",
        description=(
            "Pair a local Agent with 云驿 without copying a long-lived API key, then test "
            "persistent asynchronous messaging."
        ),
    )
    parser.add_argument(
        "--server",
        default=os.getenv("AGENTPOST_SERVER", DEFAULT_SERVER),
        help=f"AgentPost server (default: {DEFAULT_SERVER})",
    )
    parser.add_argument(
        "--profile",
        default=os.getenv("AGENTPOST_PROFILE"),
        help="local credential-vault profile; defaults to connector-type and device name",
    )
    parser.add_argument(
        "--connector-type",
        default=os.getenv("AGENTPOST_CONNECTOR_TYPE", "generic"),
        help="host type, for example codex, workbuddy, doubao_work, openclaw, hermes, or generic",
    )
    parser.add_argument(
        "--display-name",
        default=os.getenv("AGENTPOST_DISPLAY_NAME"),
        help="name shown to the Human during pairing",
    )
    parser.add_argument(
        "--device-name",
        default=os.getenv("AGENTPOST_DEVICE_NAME", platform.node() or "local-device"),
    )
    parser.add_argument(
        "--capability",
        action="append",
        default=[],
        help="structured capability; repeat for multiple values",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="print the short-lived authorization URL without opening a browser",
    )

    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("connect", help="pair once or restore the Connector from the OS vault")
    commands.add_parser("status", help="connect if needed, then report heartbeat state")

    setup = commands.add_parser(
        "setup",
        help="pair and register the local AgentPost tools in a supported host",
    )
    setup.add_argument(
        "host",
        choices=("codex", "workbuddy", "doubao_work", "openclaw", "hermes", "manus"),
    )
    setup.add_argument("--existing-agent-id", help=argparse.SUPPRESS)
    setup.add_argument("--new-agent-intent", help=argparse.SUPPRESS)

    send = commands.add_parser("send", help="send a message using the paired Agent identity")
    recipient = send.add_mutually_exclusive_group(required=True)
    recipient.add_argument("--to", help="exact Agent address")
    recipient.add_argument(
        "--recipient",
        help="natural recipient query; sends automatically only when exactly one Agent matches",
    )
    send.add_argument("--subject", default="")
    send.add_argument("--body", required=True)
    send.add_argument("--type", choices=MESSAGE_TYPES, default="message")
    send.add_argument(
        "--attachment",
        action="append",
        default=[],
        type=Path,
        help="local file to upload and attach; repeat for multiple files",
    )
    send.add_argument(
        "--ensure-host",
        choices=("codex", "workbuddy", "openclaw", "hermes"),
        help=argparse.SUPPRESS,
    )

    inbox = commands.add_parser("inbox", help="list message metadata without marking messages read")
    inbox.add_argument("--status", choices=("unread", "read", "acked"), default="unread")
    inbox.add_argument("--limit", type=_positive_int, default=50)

    read = commands.add_parser(
        "read",
        help="explicitly mark a message read and return its envelope",
    )
    read.add_argument("message_id")

    ack = commands.add_parser("ack", help="explicitly acknowledge a processed message")
    ack.add_argument("message_id")

    reply = commands.add_parser("reply", help="reply in the existing thread")
    reply.add_argument("message_id")
    reply.add_argument("--subject", default="")
    reply.add_argument("--body", required=True)
    reply.add_argument("--type", choices=REPLY_TYPES, default="response")

    commands.add_parser("rotate", help="rotate the Connector credential inside the OS vault")

    worker = commands.add_parser(
        "worker",
        help="run the durable polling worker; ACK occurs only after the local handler returns",
    )
    worker.add_argument("--once", action="store_true")
    worker.add_argument("--poll-seconds", type=_positive_float, default=30.0)
    worker.add_argument("--limit", type=_positive_int, default=50)
    worker.add_argument(
        "--auto-reply",
        action="store_true",
        help="send a deterministic receipt before ACK; never executes message content",
    )
    return parser


def _pairing_notice(instructions: PairingInstructions) -> None:
    print("authorization_required")
    print(f"user_code={instructions.user_code}")
    print(f"verification_url={instructions.verification_uri_complete}")
    print(
        "Complete approval in 星轨. This code is short-lived; no API key will be printed.",
        flush=True,
    )


def _profile(args: argparse.Namespace) -> str:
    if args.profile:
        return args.profile
    profile_scope = getattr(args, "existing_agent_id", None) or getattr(
        args,
        "new_agent_intent",
        None,
    )
    if profile_scope:
        return f"{args.connector_type}:{args.device_name[:80]}:{profile_scope}"
    return f"{args.connector_type}:{args.device_name}"


def _display_name(args: argparse.Namespace) -> str:
    return args.display_name or f"{args.connector_type} on {args.device_name}"


def _connect(args: argparse.Namespace) -> ManagedConnector:
    collection = None
    if (
        args.connector_type in {"openclaw", "hermes"}
        and sys.platform.startswith("linux")
        and not os.environ.get("DISPLAY")
        and not os.environ.get("WAYLAND_DISPLAY")
    ):
        collection = "session"
    return AgentPost.connect_managed(
        args.server,
        connector_type=args.connector_type,
        display_name=_display_name(args),
        profile=_profile(args),
        device_name=args.device_name,
        client_version=f"agentpost-connect/{__version__}",
        capabilities=args.capability,
        requested_existing_agent_id=getattr(args, "existing_agent_id", None),
        credential_store=KeyringCredentialStore(collection=collection),
        open_browser=not args.no_browser,
        on_pairing=_pairing_notice,
    )


def _mcp_command() -> Path:
    if importlib.util.find_spec("mcp") is None:
        raise ConfigurationError("Codex setup requires the agentpost[mcp,connector] extras")
    executable = "agentpost-mcp.exe" if os.name == "nt" else "agentpost-mcp"
    return Path(sys.executable).with_name(executable)


def _json(value: Any) -> None:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json", by_alias=True)
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def _message_metadata(message: Message) -> dict[str, Any]:
    return {
        "message_id": message.message_id,
        "from": message.sender.address,
        "type": message.message_type,
        "subject": message.subject,
        "status": message.delivery.status,
        "thread_id": str(message.thread_id),
        "created_at": message.created_at.isoformat(),
        "security_label": message.content.security_label,
    }


def _recipient_candidate(profile: Any) -> dict[str, Any]:
    return {
        "label": profile.label,
        "handle": profile.handle,
        "agent_id": str(profile.agent_id),
        "address": profile.address,
        "display_name": profile.display_name,
        "owner_display_name": profile.owner_display_name,
        "agent_type": profile.agent_type,
        "security_label": profile.security_label,
    }


def _resolve_recipient(client: AgentPost, args: argparse.Namespace) -> str | None:
    if args.to:
        return args.to
    resolution = client.resolve_recipient(args.recipient)
    if resolution.status == "resolved" and resolution.match is not None:
        return resolution.match.address
    _json(
        {
            "status": resolution.status,
            "reason": resolution.reason,
            "query": resolution.query,
            "candidates": [_recipient_candidate(item) for item in resolution.candidates],
            "security_label": resolution.security_label,
        }
    )
    return None


def _upload_attachments(client: AgentPost, paths: list[Path]) -> list[str]:
    attachment_ids: list[str] = []
    for raw_path in paths:
        path = raw_path.expanduser()
        if not path.is_file():
            raise ConfigurationError("attachment must be an existing local file")
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        attachment = client.attachments.upload(path, content_type=content_type)
        attachment_ids.append(str(attachment.id))
    return attachment_ids


def _configure_host(
    connector: ManagedConnector,
    host: str,
) -> (
    CodexSetupResult
    | WorkBuddySetupResult
    | DoubaoWorkSetupResult
    | OpenClawSetupResult
    | HermesSetupResult
    | ManusSetupResult
):
    options = {
        "server": connector.client.server,
        "profile": connector.profile,
        "mcp_command": _mcp_command(),
    }
    if host == "codex":
        return configure_codex_mcp(**options)
    if host == "workbuddy":
        return configure_workbuddy_mcp(**options)
    if host == "doubao_work":
        return configure_doubao_work_mcp(**options)
    if host == "manus":
        return configure_manus_mcp(**options)
    if host == "openclaw":
        collection = getattr(
            getattr(connector, "credential_store", None),
            "collection",
            "default",
        )
        return configure_openclaw_mcp(
            **options,
            keyring_collection=collection if collection != "default" else None,
        )
    if host == "hermes":
        collection = getattr(
            getattr(connector, "credential_store", None),
            "collection",
            "default",
        )
        return configure_hermes_mcp(
            **options,
            keyring_collection=collection if collection != "default" else None,
        )
    raise ConfigurationError("unsupported host setup")  # pragma: no cover


def _content_fingerprint(message: Message) -> str:
    encoded = json.dumps(
        message.content.body,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _worker_handler(*, auto_reply: bool):
    def handle(message: Message) -> None:
        fingerprint = _content_fingerprint(message)
        _json(
            {
                "event": "external_message_processed",
                **_message_metadata(message),
                "content_sha256": fingerprint,
            }
        )
        if not auto_reply or message.message_type not in {"message", "request", "task"}:
            return
        if message.message_type == "task":
            message.reply(
                "The deterministic Connector worker recorded this task without executing it.",
                subject="Deterministic task receipt",
                type="result",
                result={"status": "partial", "content_sha256": fingerprint},
                idempotency_key=f"connector-worker-reply-{message.message_id}",
            )
        else:
            message.reply(
                f"Message received; content SHA-256 is {fingerprint}.",
                subject="Deterministic receipt",
                type="response",
                idempotency_key=f"connector-worker-reply-{message.message_id}",
            )

    return handle


def _cursor_path(profile: str) -> Path:
    digest = hashlib.sha256(profile.encode()).hexdigest()[:24]
    return Path.home() / ".agentpost" / "cursors" / f"{digest}.json"


def _run_worker(args: argparse.Namespace, connector: ManagedConnector) -> int:
    worker = ConnectorWorker(
        connector,
        handler=_worker_handler(auto_reply=args.auto_reply),
        cursor_store=JsonCursorStore(_cursor_path(_profile(args))),
    )
    if args.once:
        processed = worker.run_once(max_messages=args.limit)
        _json({"event": "worker_cycle_complete", "processed": processed})
        return 0
    _json(
        {
            "event": "worker_started",
            "poll_seconds": args.poll_seconds,
            "security": "external_message_content_is_untrusted",
        }
    )
    worker.run_forever(
        stop_event=Event(),
        poll_interval_seconds=args.poll_seconds,
        sleeper=time.sleep,
    )
    return 0


def _run(args: argparse.Namespace) -> int:
    if args.command == "setup":
        args.connector_type = args.host
    elif args.command == "send" and args.ensure_host:
        args.connector_type = args.ensure_host
    if args.connector_type in {"openclaw", "hermes"} and (
        args.command == "setup" or (args.command == "send" and args.ensure_host)
    ):
        # Fail before pairing and browser authorization when the host itself cannot load MCP.
        if args.connector_type == "openclaw":
            preflight_openclaw_mcp()
        else:
            preflight_hermes_mcp()
    with _connect(args) as connector:
        client = connector.client
        credential_storage = getattr(
            getattr(connector, "credential_store", None),
            "storage_mode",
            "operating_system_vault",
        )
        if args.command == "connect":
            heartbeat = connector.heartbeat()
            _json(
                {
                    "status": "connected",
                    "address": heartbeat.agent.address,
                    "profile": connector.profile,
                    "credential_storage": credential_storage,
                }
            )
        elif args.command == "status":
            _json(connector.heartbeat())
        elif args.command == "setup":
            configured = _configure_host(connector, args.host)
            if isinstance(configured, (DoubaoWorkSetupResult, ManusSetupResult)):
                _json(
                    {
                        "status": "native_registration_required",
                        "host": args.host,
                        "profile": connector.profile,
                        "mcp_server": configured.server_name,
                        "transport": configured.transport,
                        "command": str(configured.command),
                        "args": [],
                        "env": {},
                        "approval_mode": configured.approval_mode,
                        "credential_storage": credential_storage,
                        "restart_required": configured.restart_required,
                        "next_action": (
                            "save_doubao_custom_stdio_connector"
                            if args.host == "doubao_work"
                            else "save_manus_custom_stdio_connector"
                        ),
                    }
                )
                return 0
            heartbeat = connector.heartbeat()
            result = {
                "status": "configured",
                "host": args.host,
                "address": heartbeat.agent.address,
                "profile": connector.profile,
                "mcp_server": configured.server_name,
                "approval_mode": configured.approval_mode,
                "credential_storage": credential_storage,
                "restart_required": configured.restart_required,
            }
            if credential_storage == "operating_system_vault_session":
                result["credential_persistence"] = "until_host_reboot"
            _json(result)
        elif args.command == "send":
            configured = None
            if args.ensure_host:
                configured = _configure_host(connector, args.ensure_host)
                connector.heartbeat()
            recipient_address = _resolve_recipient(client, args)
            if recipient_address is None:
                return 2
            attachment_ids = _upload_attachments(client, args.attachment)
            sent = client.send(
                recipient_address,
                args.subject,
                args.body,
                type=args.type,
                attachments=attachment_ids,
            )
            metadata = _message_metadata(sent)
            result = {
                **metadata,
                "status": "accepted",
                "delivery_status": metadata["status"],
                "to": recipient_address,
                "attachment_count": len(attachment_ids),
            }
            if configured is not None:
                result.update(
                    {
                        "host": args.ensure_host,
                        "host_configured": True,
                        "restart_required": configured.restart_required,
                    }
                )
            _json(result)
        elif args.command == "inbox":
            page = client.inbox.list(status=args.status, limit=args.limit)
            _json(
                {
                    "items": [_message_metadata(message) for message in page.items],
                    "has_more": page.has_more,
                    "next_cursor": page.next_cursor,
                }
            )
        elif args.command == "read":
            _json(client.messages.read(args.message_id))
        elif args.command == "ack":
            _json(_message_metadata(client.messages.ack(args.message_id)))
        elif args.command == "reply":
            reply_options: dict[str, Any] = {}
            if args.type == "result":
                reply_options["result"] = {"status": "completed"}
            replied = client.messages.reply(
                args.message_id,
                body=args.body,
                subject=args.subject,
                type=args.type,
                **reply_options,
            )
            _json({"status": "accepted", **_message_metadata(replied)})
        elif args.command == "rotate":
            rotation = connector.rotate_credential()
            _json(
                {
                    "status": "rotated",
                    "connector_id": rotation.connector_id,
                    "address": rotation.agent.address,
                    "rotated_at": rotation.rotated_at.isoformat(),
                    "credential_storage": "operating_system_vault",
                }
            )
        elif args.command == "worker":
            return _run_worker(args, connector)
        else:  # pragma: no cover - argparse enforces the command set
            raise RuntimeError(f"unsupported command: {args.command}")
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        return _run(_parser().parse_args(argv))
    except KeyboardInterrupt:
        print("stopped", file=sys.stderr)
        return 130
    except AgentPostError as exc:
        code = (
            exc.code if isinstance(exc, (ConfigurationError, ResponseError)) else type(exc).__name__
        )
        _json({"status": "failed", "error_code": code})
        print(f"agentpost_error code={code}", file=sys.stderr)
        return 1
    except OSError:
        _json({"status": "failed", "error_code": "local_runtime_error"})
        print("local_runtime_error", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
