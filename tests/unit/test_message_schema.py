from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas/message-envelope-v0.1.json"


@pytest.fixture(scope="module")
def validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


@pytest.fixture
def envelope() -> dict[str, object]:
    return {
        "spec_version": "0.1",
        "message_id": "msg_example_1",
        "from": {
            "agent_id": "33d7223f-f90e-4ccf-9ca8-71d156891687",
            "address": "alice@agents.local",
        },
        "to": [
            {
                "agent_id": "bd260abe-6f30-4e41-86a6-d79d48ba0676",
                "address": "bob@agents.local",
            }
        ],
        "type": "message",
        "subject": "Hello Bob",
        "content": {
            "format": "text",
            "body": "Hello Bob",
            "security_label": "external_agent_content",
        },
        "attachments": [],
        "thread_id": "579fb4ce-c33b-4f9f-a6e4-61f416d46843",
        "reply_to": None,
        "priority": "normal",
        "requires_ack": True,
        "metadata": {},
        "created_at": "2026-08-12T08:00:00Z",
        "expires_at": None,
    }


def test_valid_envelope(validator: Draft202012Validator, envelope: dict[str, object]) -> None:
    validator.validate(envelope)


def test_mvp_rejects_multiple_recipients(
    validator: Draft202012Validator, envelope: dict[str, object]
) -> None:
    candidate = copy.deepcopy(envelope)
    candidate["to"].append({"address": "carol@agents.local"})

    with pytest.raises(ValidationError):
        validator.validate(candidate)


def test_security_label_cannot_be_elevated(
    validator: Draft202012Validator, envelope: dict[str, object]
) -> None:
    candidate = copy.deepcopy(envelope)
    candidate["content"]["security_label"] = "system"

    with pytest.raises(ValidationError):
        validator.validate(candidate)


def test_task_requires_task_payload(
    validator: Draft202012Validator, envelope: dict[str, object]
) -> None:
    candidate = copy.deepcopy(envelope)
    candidate["type"] = "task"

    with pytest.raises(ValidationError):
        validator.validate(candidate)


def test_result_requires_reply_target(
    validator: Draft202012Validator, envelope: dict[str, object]
) -> None:
    candidate = copy.deepcopy(envelope)
    candidate["type"] = "result"
    candidate["result"] = {"status": "completed"}

    with pytest.raises(ValidationError):
        validator.validate(candidate)


@pytest.mark.parametrize(
    "filename", ["../secret", "/etc/passwd", "dir/file", "dir\\file", "a\x00b"]
)
def test_attachment_filename_rejects_path_syntax(
    validator: Draft202012Validator,
    envelope: dict[str, object],
    filename: str,
) -> None:
    candidate = copy.deepcopy(envelope)
    candidate["attachments"] = [
        {
            "id": "579fb4ce-c33b-4f9f-a6e4-61f416d46843",
            "filename": filename,
            "content_type": "application/octet-stream",
            "size": 1,
            "sha256": "a" * 64,
        }
    ]

    with pytest.raises(ValidationError):
        validator.validate(candidate)
