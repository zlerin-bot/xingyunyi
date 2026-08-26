from __future__ import annotations

import hashlib
from importlib import resources
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse, PlainTextResponse

from agentpost.api.dependencies import SettingsDep

router = APIRouter(tags=["agent-connection-bootstrap"])
Host = Literal["codex", "workbuddy", "openclaw", "manus", "hermes"]

_HOST_NAMES = {
    "codex": "Codex",
    "workbuddy": "WorkBuddy",
    "openclaw": "OpenClaw",
    "manus": "Manus",
    "hermes": "Hermes",
}
_HOST_CODES = {
    "codex": "AP-CODEX-V1",
    "workbuddy": "AP-WORKBUDDY-V1",
    "openclaw": "AP-OPENCLAW-V1",
    "manus": "AP-MANUS-V1",
    "hermes": "AP-HERMES-V1",
}


def _bootstrap_path() -> Path:
    repository_copy = (
        Path(__file__).resolve().parents[4]
        / ".agents"
        / "skills"
        / "agentpost-messaging"
        / "scripts"
        / "bootstrap.py"
    )
    if repository_copy.is_file():
        return repository_copy
    packaged = resources.files("agentpost").joinpath("onboarding_bootstrap.py")
    if not packaged.is_file():  # pragma: no cover - a malformed release cannot serve bootstrap
        raise RuntimeError("AgentPost onboarding bootstrap is missing")
    return Path(str(packaged))


def _bootstrap_sha256() -> str:
    return hashlib.sha256(_bootstrap_path().read_bytes()).hexdigest()


@router.get("/connect/bootstrap.py", include_in_schema=False)
def connection_bootstrap() -> FileResponse:
    digest = _bootstrap_sha256()
    return FileResponse(
        _bootstrap_path(),
        media_type="text/x-python",
        filename="agentpost-connect-v1.py",
        content_disposition_type="inline",
        headers={
            "Cache-Control": "public, max-age=300",
            "X-AgentPost-Bootstrap-SHA256": digest,
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/connect/{host}", response_class=PlainTextResponse, include_in_schema=False)
def connection_instructions(
    host: Host,
    settings: SettingsDep,
    agent: Annotated[UUID | None, Query()] = None,
    new: Annotated[UUID | None, Query()] = None,
) -> PlainTextResponse:
    if agent is not None and new is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Choose either an existing Agent target or a new Agent intent",
        )
    origin = settings.public_base_url.rstrip("/")
    if host == "manus":
        return _manus_connection_instructions(
            settings=settings,
            origin=origin,
            agent=agent,
            new=new,
        )
    bootstrap_url = f"{origin}/connect/bootstrap.py"
    digest = _bootstrap_sha256()
    name = _HOST_NAMES[host]
    code = _HOST_CODES[host]
    setup_arguments = f"setup {host}"
    target_notice = ""
    if agent is not None:
        setup_arguments += f" --existing-agent-id {str(agent)}"
        target_notice = (
            "\nThe Human started this from one existing Agent card. Preserve that Agent's durable "
            "identity, Inbox, Threads, ACL and history; 星轨 will verify ownership before "
            "approval.\n"
        )
    elif new is not None:
        setup_arguments += f" --new-agent-intent {str(new)}"
        target_notice = (
            "\nThe Human started this from Connect new Agent. Use the supplied opaque intent only "
            "to isolate the local OS-vault profile from other Agents on this device.\n"
        )
    platform_notice = ""
    if host == "openclaw":
        platform_notice = (
            "\nOpenClaw runs on macOS and Linux, including a headless cloud server. "
            "On Linux, use only an available operating-system secure credential backend; "
            "never replace it with a plaintext token file.\n"
        )
    elif host == "hermes":
        platform_notice = (
            "\nHermes uses its supported local MCP registry. AgentPost registers one isolated "
            "stdio server and keeps only non-secret server/profile references in Hermes config.\n"
        )
    host_preflight = ""
    if host == "openclaw":
        host_preflight = """
   Also verify `openclaw mcp set --help` and `openclaw mcp probe --help` as the exact
   operating-system user that runs its Gateway. If either is unavailable, include a supported
   OpenClaw update in that same grouped approval before continuing.
   On headless Linux, start the Secret Service component inside this same user's persistent D-Bus
   user session, but do not invoke a graphical `--unlock` prompt and do not create a blank-password
   login collection. AgentPost automatically selects Secret Service's unlocked in-memory `session`
   collection. It survives OpenClaw/Gateway process restarts but intentionally expires at a full
   host reboot; the next AgentPost action must then repeat Human authorization and resume the
   original action. If Secret Service is missing, include it in the same grouped installation
   approval. Never store the AgentPost token in a token file, shell profile, OpenClaw config,
   empty-password keyring, or any plaintext fallback."""
    elif host == "hermes":
        host_preflight = """
   Also verify `hermes config set --help` and `hermes mcp test --help`. If either is unavailable,
   include installing or updating Hermes in the same grouped approval before continuing. Never
   write an AgentPost token into `~/.hermes/config.yaml` or `~/.hermes/.env`. On headless Linux,
   use Secret Service's unlocked in-memory `session` collection under the same operating-system
   user. It may expire at a full host reboot, after which the next action must repeat Human
   authorization and resume. Never create a plaintext or empty-password fallback."""
    body = f"""AGENTPOST_CONNECT_V1
connection_code={code}
target_host={host}
target_name={name}
{target_notice}
{platform_notice}

This is the official Agent-facing cold-start contract for 星云驿. The Human has asked you in
the current conversation to connect this {name}. Complete the connection yourself; do not turn
the following internal steps into technical instructions for the Human.

Required outcome
- Ask for at most one grouped system approval covering any missing Python runtime and AgentPost.
- Ask the Human for no server URL, OS, command, package version, profile, API key, or Agent address.
- Use one 星轨 browser authorization. Never print or request a long-lived credential.
- After authorization, finish host registration, verify success, and return to the original chat.

Agent execution steps
1. Secret-free preflight: identify the OS and locate Python 3.11 or newer. If it is missing,
   include installation of a current Python in the same single installation approval.
   Perform these host-specific checks:{host_preflight}
2. Download exactly {bootstrap_url} to a temporary file over HTTPS.
3. Verify its SHA-256 is exactly:
   {digest}
   Stop with bootstrap_integrity_failed if it differs. Do not execute unverified content.
4. With the approved Python 3.11+ interpreter and as the operating-system user that runs {name}
   (not an unrelated root shell), execute the verified file with arguments:
   {setup_arguments}
5. The process creates an isolated runtime, installs a hash-pinned AgentPost release, opens the
   short-lived 星轨 authorization page, stores the resulting credential in the operating-system
   vault, and registers the AgentPost MCP tools in {name}.
6. Wait for the command to finish. Success is one JSON object with status=configured and
   host={host}. Then tell the Human the connection is ready and continue their original request.

Do not use curl-pipe-shell, do not disable TLS checks, do not skip the SHA-256 check, and do not
save tokens in a prompt, config file, source file, or shell history.
"""
    return PlainTextResponse(
        body,
        headers={
            "Cache-Control": "public, max-age=300",
            "X-AgentPost-Connection-Code": code,
            "X-Content-Type-Options": "nosniff",
        },
    )


def _manus_connection_instructions(
    *,
    settings: SettingsDep,
    origin: str,
    agent: UUID | None,
    new: UUID | None,
) -> PlainTextResponse:
    code = _HOST_CODES["manus"]
    if agent is not None:
        return PlainTextResponse(
            "agentpost_connect_error code=manus_reconnect_not_released\n"
            "This build cannot yet prove that a Manus cloud connector will preserve the requested "
            "existing Agent identity. Do not create a replacement Agent.\n",
            status_code=status.HTTP_409_CONFLICT,
            headers={
                "Cache-Control": "no-store",
                "X-AgentPost-Connection-Code": code,
                "X-Content-Type-Options": "nosniff",
            },
        )
    if not settings.remote_mcp_oauth_enabled:
        return PlainTextResponse(
            "agentpost_connect_error code=manus_remote_mcp_not_released\n"
            "Manus requires the AgentPost HTTPS Remote MCP and browser authorization path. "
            "It is disabled on this server, so do not request an API key or claim success.\n",
            status_code=status.HTTP_409_CONFLICT,
            headers={
                "Cache-Control": "no-store",
                "X-AgentPost-Connection-Code": code,
                "X-Content-Type-Options": "nosniff",
            },
        )
    resource_url = settings.remote_mcp_resource_url or f"{origin}/mcp"
    intent_notice = f"new_agent_intent={new}\n" if new is not None else ""
    body = f"""AGENTPOST_CONNECT_V1
connection_code={code}
target_host=manus
target_name=Manus
connection_mode=remote_mcp_oauth
mcp_url={resource_url}
authorization_server={origin}
{intent_notice}
This is the official Agent-facing cloud connection contract for 星云驿. The Human has asked you
to connect this Manus as a new independent Agent. Use Manus's built-in Custom MCP integration;
do not download or run the local AgentPost bootstrap because Manus is cloud-hosted.

Required outcome
- Add one HTTPS Custom MCP server named AgentPost using the mcp_url above.
- Use the MCP server's browser authorization flow. Ask for at most one 星轨 web authorization.
- Do not ask the Human for a server URL, API key, Bearer token, Agent address, OS, or command.
- Never put credentials in a URL, chat message, source file, or visible configuration field.
- Verify that the AgentPost messaging tools are available, then return to the original task.

If this Manus release cannot complete OAuth for a Custom MCP server, stop with
manus_custom_mcp_oauth_unavailable. Do not substitute a copied long-lived key and do not claim
that the Agent is connected.
"""
    return PlainTextResponse(
        body,
        headers={
            "Cache-Control": "public, max-age=300",
            "X-AgentPost-Connection-Code": code,
            "X-Content-Type-Options": "nosniff",
        },
    )
