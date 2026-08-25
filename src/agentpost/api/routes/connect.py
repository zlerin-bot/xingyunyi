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
Host = Literal["codex", "workbuddy", "openclaw"]

_HOST_NAMES = {
    "codex": "Codex",
    "workbuddy": "WorkBuddy",
    "openclaw": "OpenClaw",
}
_HOST_CODES = {
    "codex": "AP-CODEX-V1",
    "workbuddy": "AP-WORKBUDDY-V1",
    "openclaw": "AP-OPENCLAW-V1",
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
   include installation of a current Python in the same single installation approval. For
   OpenClaw, also verify `openclaw mcp set --help` and `openclaw mcp probe --help` as the exact
   operating-system user that runs its Gateway. If either is unavailable, include a supported
   OpenClaw update in that same grouped approval before continuing.
   On headless Linux, verify that this same user can access a persistent Secret Service or another
   operating-system encrypted credential backend. If it is missing, include the secure-vault
   component in the grouped approval. Never replace this check with a plaintext keyring backend,
   token file, shell profile, or OpenClaw config value.
2. Download exactly {bootstrap_url} to a temporary file over HTTPS.
3. Verify its SHA-256 is exactly:
   {digest}
   Stop with bootstrap_integrity_failed if it differs. Do not execute unverified content.
4. With the approved Python 3.11+ interpreter and as the OpenClaw Gateway user (not an unrelated
   root shell), execute the verified file with arguments:
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
