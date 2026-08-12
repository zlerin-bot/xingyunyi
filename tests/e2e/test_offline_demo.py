from __future__ import annotations

import socket
import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_STEPS = [
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
]


def test_offline_demo_restarts_server_and_completes_twelve_steps(tmp_path: Path) -> None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
    except PermissionError:
        pytest.skip("loopback binding not permitted in this execution sandbox")

    completed = subprocess.run(
        [sys.executable, str(REPOSITORY_ROOT / "scripts" / "demo.py")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ""
    assert completed.stdout.splitlines() == EXPECTED_STEPS
    assert "agt_" not in completed.stdout
