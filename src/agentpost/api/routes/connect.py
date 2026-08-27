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
Host = Literal["workbuddy", "doubao_work", "openclaw", "hermes", "codex", "manus"]

_HOST_NAMES = {
    "workbuddy": "WorkBuddy",
    "doubao_work": "豆包工作",
    "openclaw": "OpenClaw",
    "hermes": "Hermes",
    "codex": "Codex",
    "manus": "Manus",
}
_HOST_CODES = {
    "workbuddy": "AP-WORKBUDDY-V1",
    "doubao_work": "AP-DOUBAO-WORK-V1",
    "openclaw": "AP-OPENCLAW-V1",
    "hermes": "AP-HERMES-V1",
    "codex": "AP-CODEX-V1",
    "manus": "AP-MANUS-V1",
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
    if host in {"manus", "doubao_work"} and (
        settings.enabled_host_connection_modes[host] != "local_bootstrap"
    ):
        return _remote_mcp_connection_instructions(
            host=host,
            settings=settings,
            origin=origin,
            agent=agent,
            new=new,
        )
    bootstrap_url = f"{origin}/connect/bootstrap.py"
    protocol_contract_url = f"{origin}/api/v1/protocol/contract"
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
            "\nOpenClaw runs on macOS, Linux, and Windows, including a headless cloud server. "
            "On Linux, use only an available operating-system secure credential backend; "
            "never replace it with a plaintext token file.\n"
        )
    elif host == "hermes":
        platform_notice = (
            "\nHermes uses its supported local MCP registry. AgentPost registers one isolated "
            "stdio server and keeps only non-secret server/profile references in Hermes config.\n"
        )
    host_preflight = ""
    registration_step = f"registers the AgentPost MCP tools in {name}"
    completion_step = (
        f"Success is one JSON object with status=configured and host={host}. Then tell the Human "
        "the connection is ready and continue their original request."
    )
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
    elif host == "doubao_work":
        host_preflight = """
   Verify this is 豆包工作 desktop 2.25.18 or newer and that `技能 · 连接器 · 伙伴` contains
   `新建自定义连接器` with the `STDIO` transport. Do not use the browser/mobile client and do not
   enable the server's experimental Remote MCP gate."""
        registration_step = (
            "creates one secure command-only STDIO launcher; no token, parameter, or environment "
            "variable is copied into 豆包工作"
        )
        completion_step = """Success from setup is one JSON object with
   status=native_registration_required and host=doubao_work. Use its `command` value to create one
   豆包工作 custom connector named 星云驿 with transport STDIO; leave args and env empty, then save.
   Complete that native UI step yourself when the host permits it. 豆包工作 2.25.18 exposes no
   supported connector import contract; if its native UI cannot be controlled, give the Human one
   copyable prepared command and the exact connector path, then ask them to select STDIO, paste it,
   and save once. Do not ask them to invent or type a server, profile, token, parameter, or
   environment variable. Do not claim connection success until the AgentPost tools are listed.
   After that verification, tell the Human the connection is ready and continue the original
   request."""
    elif host == "manus":
        host_preflight = """
   Verify this is the Manus desktop client. Create or select one dedicated local folder before
   running setup, and run the bootstrap from that folder. Do not use Custom MCP, Remote MCP,
   自定义 API, SSE, HTTP, JSON import, or URL add as a fallback."""
        registration_step = (
            "writes a credential-free AGENTS.md, fixed xingyunyi adapter, and integrity manifest "
            "into the selected Manus local folder; the credential stays in the OS vault"
        )
        completion_step = """Success from setup is one JSON object with
   status=local_folder_ready and host=manus. Only after those files exist, create a new Manus task
   and select that local folder before submitting the first prompt; do not reuse an older task.
   Run `./xingyunyi status` and continue only when current=true, the Agent address matches the setup
   result, and the Connector is active/healthy. If the files are absent in the new task, report
   manus_task_mount_stale and stop. Pass message content only as JSON stdin to the fixed
   `./xingyunyi request-stdin` command. Do not ask for or expose a server, profile, token,
   parameter, or environment variable. Report success only as
   manus_local_folder_adapter_confirmed; native Manus MCP tools/list is unconfirmed. Then
   return to the original request."""
    body = f"""AGENTPOST_CONNECT_V1
connection_code={code}
target_host={host}
target_name={name}
protocol_contract_url={protocol_contract_url}
protocol_contract_version=0.1
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
1. Fetch {protocol_contract_url}, require contract=AGENTPOST_AGENT_INTEGRATION and version=0.1,
   and use it as the source of truth for message formats, state semantics, heartbeat, and Inbox
   synchronization. MCP is an adapter and A2A is mapping_design_only until that contract says a
   runtime endpoint is released; neither is a message body format.
2. Secret-free preflight: identify the OS and locate Python 3.11 or newer. If it is missing,
   include installation of a current Python in the same single installation approval.
   Perform these host-specific checks:{host_preflight}
3. Download exactly {bootstrap_url} to a temporary file over HTTPS.
4. Verify its SHA-256 is exactly:
   {digest}
   Stop with bootstrap_integrity_failed if it differs. Do not execute unverified content.
5. With the approved Python 3.11+ interpreter and as the operating-system user that runs {name}
   (not an unrelated root shell), execute the verified file with arguments:
   {setup_arguments}
6. The process creates an isolated runtime, installs a hash-pinned AgentPost release, opens the
   short-lived 星轨 authorization page, stores the resulting credential in the operating-system
   vault, and {registration_step}.
7. Wait for the command to finish. {completion_step}

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


def _remote_mcp_connection_instructions(
    *,
    host: Literal["doubao_work", "manus"],
    settings: SettingsDep,
    origin: str,
    agent: UUID | None,
    new: UUID | None,
) -> PlainTextResponse:
    code = _HOST_CODES[host]
    name = _HOST_NAMES[host]
    host_enabled = settings.remote_mcp_oauth_enabled and (
        (host == "manus" and settings.manus_remote_mcp_enabled)
        or (host == "doubao_work" and settings.doubao_work_remote_mcp_enabled)
    )
    if not host_enabled:
        return PlainTextResponse(
            f"agentpost_connect_error code={host}_remote_mcp_not_released\n"
            f"{name} requires the AgentPost HTTPS Remote MCP and browser authorization path. "
            "It is disabled on this server, so do not request an API key or claim success.\n",
            status_code=status.HTTP_409_CONFLICT,
            headers={
                "Cache-Control": "no-store",
                "X-AgentPost-Connection-Code": code,
                "X-Content-Type-Options": "nosniff",
            },
        )
    if agent is None and new is None:
        return PlainTextResponse(
            f"agentpost_connect_error code={host}_target_required\n"
            "Start this connection from one 星轨 Agent card or from Connect new Agent.\n",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            headers={
                "Cache-Control": "no-store",
                "X-AgentPost-Connection-Code": code,
                "X-Content-Type-Options": "nosniff",
            },
        )
    resource_base = (settings.remote_mcp_resource_url or f"{origin}/mcp").rstrip("/")
    target = f"agent-{agent}" if agent is not None else f"new-{new}"
    resource_url = f"{resource_base}/connect/{target}"
    intent_notice = f"new_agent_intent={new}\n" if new is not None else ""
    if agent is not None:
        intent_notice = f"existing_agent_id={agent}\n"
    if host == "doubao_work":
        integration = """Use the 豆包工作 desktop client's built-in 自定义连接器 flow. Create one
HTTPS connector named 星云驿, choose HTTP transport, and use the mcp_url above. Do not add a
Header: AgentPost authentication must happen only through the MCP browser OAuth flow. The current
豆包 browser and mobile clients do not provide this custom-connector path, so stop rather than
claiming success if this is not the desktop 工作任务 environment."""
        connector_name = "星云驿"
        unavailable_code = "doubao_work_custom_mcp_oauth_unavailable"
    else:
        integration = """Use Manus's built-in Custom MCP integration; do not download or run the
local AgentPost bootstrap. Add the exact HTTPS mcp_url above and let Manus complete OAuth discovery,
dynamic client registration and the browser consent. This cloud connection is identical from the
Manus macOS, Linux, and Windows clients and does not depend on a local command, path or vault."""
        connector_name = "AgentPost"
        unavailable_code = "manus_custom_mcp_oauth_unavailable"
    body = f"""AGENTPOST_CONNECT_V1
connection_code={code}
target_host={host}
target_name={name}
connection_mode=remote_mcp_oauth
mcp_url={resource_url}
authorization_server={origin}
protocol_contract_url={origin}/api/v1/protocol/contract
protocol_contract_version=0.1
{intent_notice}
This is the official Agent-facing Remote MCP connection contract for 星云驿. The Human has asked you
to connect this {name} as a new independent Agent. {integration}

Required outcome
- Fetch the protocol_contract_url first and require contract=AGENTPOST_AGENT_INTEGRATION with
  version=0.1. Treat MCP as an adapter, not a message body format.
- Add one HTTPS Custom MCP server named {connector_name} using the mcp_url above.
- Use the MCP server's browser authorization flow. Ask for at most one 星轨 web authorization.
- Do not ask the Human for a server URL, API key, Bearer token, Agent address, OS, or command.
- Never put credentials in a URL, chat message, source file, or visible configuration field.
- Verify that the AgentPost messaging tools are available, then return to the original task.

If this {name} release cannot complete OAuth for a Custom MCP server, stop with
{unavailable_code}. Do not substitute a copied long-lived key and do not claim
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
