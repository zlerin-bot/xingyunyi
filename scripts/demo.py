#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATHS = (
    REPOSITORY_ROOT / "src",
    REPOSITORY_ROOT / "sdk" / "python" / "src",
)
for source_path in reversed(SOURCE_PATHS):
    source = str(source_path)
    if source not in sys.path:
        sys.path.insert(0, source)

import httpx  # noqa: E402
from agentpost_sdk import AgentPostError  # noqa: E402

from agentpost import AgentPost  # noqa: E402

DEMO_STEPS = (
    "1. Create Alice",
    "2. Create Bob",
    "3. Alice: Sending message to Bob...",
    "4. Bob is offline.",
    "5. Message accepted and persisted.",
    "6. Restart AgentPost server.",
    "7. Start Bob.",
    "8. Bob: 1 unread message from Alice.",
    "9. Bob reads message.",
    "10. Bob ACKs message.",
    "11. Bob replies.",
    "12. Alice: 1 new reply from Bob.",
)


class DemoError(RuntimeError):
    """A sanitized, user-facing demo failure."""


def _pythonpath() -> str:
    paths = [str(path) for path in SOURCE_PATHS]
    inherited = os.environ.get("PYTHONPATH")
    if inherited:
        paths.append(inherited)
    return os.pathsep.join(paths)


def _runtime_environment(data_dir: Path) -> dict[str, str]:
    database_path = (data_dir / "agentpost-demo.db").resolve()
    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONPATH": _pythonpath(),
            "AGENTPOST_ENVIRONMENT": "test",
            "AGENTPOST_DATABASE_URL": f"sqlite+pysqlite:///{database_path}",
            "AGENTPOST_STORAGE_PATH": str((data_dir / "attachments").resolve()),
            "AGENTPOST_LOG_LEVEL": "WARNING",
            "AGENTPOST_API_KEY_PEPPER": secrets.token_urlsafe(32),
            "AGENTPOST_CURSOR_SECRET": secrets.token_urlsafe(32),
            "AGENTPOST_REGISTRATION_TOKEN": "",
        }
    )
    return environment


def _available_port() -> int:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            return int(listener.getsockname()[1])
    except OSError as exc:
        raise DemoError("could not reserve a localhost port for the demo API") from exc


def _migrate(environment: dict[str, str]) -> None:
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
            cwd=REPOSITORY_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise DemoError("database migration could not be started") from exc
    if completed.returncode != 0:
        raise DemoError("database migration failed; run `uv sync --extra dev` first")


def _start_server(
    *, environment: dict[str, str], port: int, log_path: Path
) -> subprocess.Popen[bytes]:
    log_stream = log_path.open("ab")
    try:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "agentpost.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--log-level",
                "warning",
                "--no-access-log",
            ],
            cwd=REPOSITORY_ROOT,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=log_stream,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    finally:
        log_stream.close()
    return process


def _wait_for_health(process: subprocess.Popen[bytes], server: str) -> None:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise DemoError("AgentPost API stopped before becoming healthy")
        try:
            response = httpx.get(f"{server}/health", timeout=0.5)
            if response.status_code == 200 and response.json().get("status") == "ok":
                ready = httpx.get(f"{server}/ready", timeout=0.5)
                if ready.status_code == 200:
                    return
        except (httpx.HTTPError, ValueError):
            pass
        time.sleep(0.1)
    raise DemoError("AgentPost API did not become healthy within 15 seconds")


def _stop_server(process: subprocess.Popen[bytes] | None) -> bool:
    if process is None:
        return True
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    return process.poll() is not None


def _register_agent(server: str, address: str) -> dict[str, Any]:
    try:
        response = httpx.post(
            f"{server}/api/v1/agents",
            json={"address": address, "display_name": address.partition("@")[0].title()},
            timeout=5,
        )
    except httpx.HTTPError as exc:
        raise DemoError(f"could not register {address}") from exc
    if response.status_code != 201:
        raise DemoError(f"server rejected registration for {address}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise DemoError("registration returned a non-JSON response") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("api_key"), str):
        raise DemoError("registration returned a malformed response")
    return payload


def _run_scenario(
    *,
    data_dir: Path,
    emit: Callable[[str], None],
) -> dict[str, Any]:
    environment = _runtime_environment(data_dir)
    _migrate(environment)
    port = _available_port()
    server = f"http://127.0.0.1:{port}"
    log_path = data_dir / "agentpost-server.log"
    process: subprocess.Popen[bytes] | None = None
    first_process_stopped = False
    steps: list[str] = []

    def step(index: int) -> None:
        value = DEMO_STEPS[index - 1]
        steps.append(value)
        emit(value)

    try:
        process = _start_server(environment=environment, port=port, log_path=log_path)
        _wait_for_health(process, server)

        step(1)
        alice = _register_agent(server, "alice@agents.local")
        step(2)
        bob = _register_agent(server, "bob@agents.local")

        step(3)
        with AgentPost(server, alice["api_key"], timeout=5) as alice_client:
            sent = alice_client.send(
                "bob@agents.local",
                "Hello Bob",
                "Hello Bob",
                idempotency_key="demo-alice-hello-bob",
            )
        if sent.delivery.status != "delivered":
            raise DemoError("the initial message was not delivered to Bob's inbox")
        step(4)
        step(5)

        step(6)
        first_process_stopped = _stop_server(process)
        if not first_process_stopped:
            raise DemoError("the first AgentPost API process did not stop")
        process = _start_server(environment=environment, port=port, log_path=log_path)
        _wait_for_health(process, server)

        step(7)
        with AgentPost(server, bob["api_key"], timeout=5) as bob_client:
            unread = bob_client.inbox.unread()
            if len(unread.items) != 1 or unread.items[0].message_id != sent.message_id:
                raise DemoError("Bob did not receive exactly the persisted unread message")
            received = unread.items[0]
            step(8)
            read_message = received.mark_read()
            if read_message.delivery.status != "read":
                raise DemoError("Bob could not mark the message read")
            step(9)
            acked_message = received.ack()
            if acked_message.delivery.status != "acked":
                raise DemoError("Bob could not acknowledge the message")
            step(10)
            reply = received.reply(
                "Received.",
                subject="Re: Hello Bob",
                idempotency_key="demo-bob-received",
            )
            step(11)

        with AgentPost(server, alice["api_key"], timeout=5) as alice_client:
            alice_unread = alice_client.inbox.unread()
        if len(alice_unread.items) != 1 or alice_unread.items[0].message_id != reply.message_id:
            raise DemoError("Alice did not receive Bob's reply")
        if reply.reply_to != sent.message_id or reply.thread_id != sent.thread_id:
            raise DemoError("the reply did not preserve reply and thread linkage")
        step(12)

        return {
            "success": True,
            "steps": steps,
            "server_restarted": first_process_stopped,
            "message_id": sent.message_id,
            "message_status": acked_message.delivery.status,
            "reply_message_id": reply.message_id,
            "reply_to": reply.reply_to,
            "thread_id": str(reply.thread_id),
            "bob_unread_count": len(unread.items),
            "alice_reply_count": len(alice_unread.items),
        }
    finally:
        _stop_server(process)


def run_demo(
    *,
    keep_data: bool = False,
    data_dir: Path | None = None,
    emit: Callable[[str], None] = print,
) -> dict[str, Any]:
    temporary: tempfile.TemporaryDirectory[str] | None = None
    if data_dir is not None:
        working_directory = data_dir.resolve()
        working_directory.mkdir(parents=True, exist_ok=True)
    elif keep_data:
        working_directory = Path(tempfile.mkdtemp(prefix="agentpost-demo-"))
    else:
        temporary = tempfile.TemporaryDirectory(prefix="agentpost-demo-")
        working_directory = Path(temporary.name)

    try:
        summary = _run_scenario(data_dir=working_directory, emit=emit)
        if keep_data:
            summary["data_dir"] = str(working_directory)
        return summary
    finally:
        if temporary is not None:
            temporary.cleanup()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the offline AgentPost acceptance demo")
    parser.add_argument("--json", action="store_true", help="emit a machine-readable summary")
    parser.add_argument(
        "--keep-data",
        action="store_true",
        help="retain the temporary SQLite database, attachments, and server log",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        summary = run_demo(
            keep_data=arguments.keep_data,
            emit=(lambda _: None) if arguments.json else print,
        )
    except (DemoError, AgentPostError, httpx.HTTPError, OSError) as exc:
        if arguments.json:
            print(json.dumps({"success": False, "error": str(exc)}, sort_keys=True))
        else:
            print(f"Demo failed: {exc}", file=sys.stderr)
        return 1
    if arguments.json:
        print(json.dumps(summary, sort_keys=True))
    elif arguments.keep_data:
        print(f"Demo data retained at: {summary['data_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
