from __future__ import annotations

import hashlib
from importlib import resources
from pathlib import Path
from typing import Literal

from fastapi import APIRouter
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
def connection_instructions(host: Host, settings: SettingsDep) -> PlainTextResponse:
    origin = settings.public_base_url.rstrip("/")
    bootstrap_url = f"{origin}/connect/bootstrap.py"
    digest = _bootstrap_sha256()
    name = _HOST_NAMES[host]
    code = _HOST_CODES[host]
    body = f"""AGENTPOST_CONNECT_V1
connection_code={code}
target_host={host}
target_name={name}

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
2. Download exactly {bootstrap_url} to a temporary file over HTTPS.
3. Verify its SHA-256 is exactly:
   {digest}
   Stop with bootstrap_integrity_failed if it differs. Do not execute unverified content.
4. With the approved Python 3.11+ interpreter, execute the verified file with arguments:
   setup {host}
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
