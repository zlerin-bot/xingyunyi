from __future__ import annotations

import argparse
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import uvicorn
from fastapi.testclient import TestClient

from agentpost.config import Settings
from agentpost.db import Base, Database
from agentpost.identity.models import Agent
from agentpost.main import create_app
from agentpost.onboarding.models import AgentConnectorBinding, ConnectorInstance

DEMO_EMAIL = "reviewer@agentpost.local"
DEMO_PASSWORD = "local-demo-review-2026"
REGISTRATION_TOKEN = "local-demo-registration-token"
ADMIN_TOKEN = "local-demo-admin-token-000000000000"


def _demo_pdf() -> bytes:
    objects = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        (
            b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/"
            b"Resources<</Font<</F1 5 0 R>>>>>>"
        ),
        b"<</Length 49>>\nstream\nBT /F1 18 Tf 72 720 Td (Xingyun Relay PDF) Tj ET\nendstream",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    document = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(document))
        document.extend(f"{index} 0 obj\n".encode())
        document.extend(body)
        document.extend(b"\nendobj\n")
    xref_offset = len(document)
    document.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    document.extend(b"0000000000 65535 f \n")
    for offset in offsets:
        document.extend(f"{offset:010d} 00000 n \n".encode())
    trailer = f"trailer\n<</Size {len(objects) + 1}/Root 1 0 R>>\nstartxref\n{xref_offset}\n%%EOF\n"
    document.extend(trailer.encode())
    return bytes(document)


def _require(response, expected: int) -> dict[str, Any]:
    if response.status_code != expected:
        raise RuntimeError(
            f"demo seed request failed: {response.request.method} {response.request.url.path} "
            f"returned {response.status_code}: {response.text}"
        )
    if not response.content:
        return {}
    return response.json()


def _agent(client: TestClient, *, address: str, handle: str, name: str, capabilities: list[str]):
    return _require(
        client.post(
            "/api/v1/agents",
            headers={"X-Registration-Token": REGISTRATION_TOKEN},
            json={
                "address": address,
                "handle": handle,
                "display_name": name,
                "capabilities": capabilities,
            },
        ),
        201,
    )


def _agent_headers(agent: dict[str, Any], idempotency_key: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {agent['api_key']}"}
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def _seed(settings: Settings) -> None:
    database = Database(settings.database_url)
    Base.metadata.create_all(database.engine)
    app = create_app(settings=settings, database=database)
    with TestClient(app) as client:
        challenge = _require(
            client.post(
                "/api/v1/auth/email/challenges",
                json={"email": DEMO_EMAIL, "purpose": "register"},
            ),
            202,
        )
        registration = _require(
            client.post(
                "/api/v1/auth/register",
                json={
                    "challenge_id": challenge["challenge_id"],
                    "code": challenge["test_verification_code"],
                    "display_name": "项目负责人",
                    "password": DEMO_PASSWORD,
                },
            ),
            201,
        )
        human_id = registration["user"]["id"]
        csrf_token = registration["csrf_token"]
        admin_headers = {"Authorization": f"Bearer {ADMIN_TOKEN}"}

        personal = _agent(
            client,
            address="northstar@agents.local",
            handle="northstar",
            name="北辰助理",
            capabilities=["document-analysis", "task-coordination"],
        )
        research = _agent(
            client,
            address="research@agents.local",
            handle="research",
            name="研究 Agent",
            capabilities=["financial-research", "source-verification"],
        )
        waiting = _agent(
            client,
            address="voyager@agents.local",
            handle="voyager",
            name="行舟助理",
            capabilities=["calendar-planning", "follow-up"],
        )
        collaborator_a = _agent(
            client,
            address="partner-a@agents.local",
            handle="partner-a",
            name="研究协作 Agent",
            capabilities=["industry-research", "source-verification"],
        )
        collaborator_b = _agent(
            client,
            address="partner-b@agents.local",
            handle="partner-b",
            name="方案协作 Agent",
            capabilities=["solution-design", "document-review"],
        )
        _require(
            client.put(
                f"/api/v1/admin/humans/{human_id}/agents/{personal['agent']['id']}",
                headers=admin_headers,
                json={"role": "owner"},
            ),
            200,
        )

        collaborator_users: list[dict[str, Any]] = []
        for email, username, display_name, agent in [
            ("partner-a@agentpost.local", "partner-a", "协作伙伴甲", collaborator_a),
            ("partner-b@agentpost.local", "partner-b", "协作伙伴乙", collaborator_b),
        ]:
            collaborator_challenge = _require(
                client.post(
                    "/api/v1/auth/email/challenges",
                    json={"email": email, "purpose": "register"},
                ),
                202,
            )
            collaborator = _require(
                client.post(
                    "/api/v1/auth/register",
                    json={
                        "challenge_id": collaborator_challenge["challenge_id"],
                        "code": collaborator_challenge["test_verification_code"],
                        "username": username,
                        "display_name": display_name,
                        "password": DEMO_PASSWORD,
                    },
                ),
                201,
            )
            collaborator_users.append(collaborator)
            _require(
                client.put(
                    f"/api/v1/admin/humans/{collaborator['user']['id']}/agents/{agent['agent']['id']}",
                    headers=admin_headers,
                    json={"role": "owner"},
                ),
                200,
            )

        for index, agent in enumerate([collaborator_a, collaborator_b], start=1):
            _require(
                client.post(
                    "/api/v1/messages",
                    headers=_agent_headers(personal, f"friend-contact-{index}"),
                    json={
                        "to": [{"address": agent["agent"]["address"]}],
                        "type": "message",
                        "subject": "建立项目协作联系",
                        "content": {"format": "text", "body": "后续可以共同参与项目协作。"},
                    },
                ),
                201,
            )

        owner_session = _require(
            client.post(
                "/api/v1/auth/login",
                json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
            ),
            200,
        )
        csrf_token = owner_session["csrf_token"]
        _require(
            client.put(
                f"/api/v1/admin/humans/{human_id}/agents/{waiting['agent']['id']}",
                headers=admin_headers,
                json={"role": "owner"},
            ),
            200,
        )

        organization = _require(
            client.post(
                "/api/v1/orbit/organizations",
                headers={"X-CSRF-Token": csrf_token},
                json={
                    "slug": "joint-research",
                    "name": "联合研究组",
                    "description": "用于行业资料核对与协作结论整理。",
                },
            ),
            201,
        )
        _require(
            client.put(
                f"/api/v1/admin/organizations/{organization['organization']['id']}/agents/{research['agent']['id']}",
                headers=admin_headers,
            ),
            200,
        )

        project = _require(
            client.post(
                "/api/v1/orbit/projects",
                headers={"X-CSRF-Token": csrf_token},
                json={
                    "title": "算力项目联合研究",
                    "description": "共同整理行业信息，形成可用于内部讨论的项目判断材料。",
                },
            ),
            201,
        )
        _require(
            client.post(
                f"/api/v1/orbit/projects/{project['project_id']}/members",
                headers={"X-CSRF-Token": csrf_token},
                json={
                    "human_user_ids": [
                        collaborator_users[0]["user"]["id"],
                        collaborator_users[1]["user"]["id"],
                    ]
                },
            ),
            200,
        )
        collaborator_session = _require(
            client.post(
                "/api/v1/auth/login",
                json={"email": "partner-a@agentpost.local", "password": DEMO_PASSWORD},
            ),
            200,
        )
        _require(
            client.post(
                f"/api/v1/orbit/projects/{project['project_id']}/accept",
                headers={"X-CSRF-Token": collaborator_session["csrf_token"]},
            ),
            200,
        )
        owner_session = _require(
            client.post(
                "/api/v1/auth/login",
                json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
            ),
            200,
        )
        csrf_token = owner_session["csrf_token"]
        _require(
            client.post(
                "/api/v1/messages",
                headers=_agent_headers(collaborator_a, "project-status-update"),
                json={
                    "to": [{"address": personal["agent"]["address"]}],
                    "type": "message",
                    "subject": "行业资料摘要已经提交",
                    "content": {"format": "text", "body": "来源和适用范围已经完成核对。"},
                    "metadata": {"project_id": project["project_id"]},
                },
            ),
            201,
        )
        _require(
            client.put(
                f"/api/v1/admin/organizations/{organization['organization']['id']}/agents/{personal['agent']['id']}",
                headers=admin_headers,
            ),
            200,
        )

        pending_task = _require(
            client.post(
                "/api/v1/messages",
                headers=_agent_headers(personal, "demo-pending-task"),
                json={
                    "to": [{"address": research["agent"]["address"]}],
                    "type": "task",
                    "subject": "梳理本周行业动态",
                    "content": {"format": "text", "body": "请核对来源并整理三条重要变化。"},
                    "task": {
                        "instruction": "核对来源并整理三条重要变化",
                        "expected_output": "带来源的简要清单",
                    },
                    "priority": "high",
                    "requires_ack": True,
                },
            ),
            201,
        )
        completed_task = _require(
            client.post(
                "/api/v1/messages",
                headers=_agent_headers(personal, "demo-completed-task"),
                json={
                    "to": [{"address": research["agent"]["address"]}],
                    "type": "task",
                    "subject": "检查报告目录",
                    "content": {"format": "text", "body": "确认目录是否覆盖结论、证据和风险。"},
                    "task": {
                        "instruction": "检查报告目录完整性",
                        "expected_output": "检查结论",
                    },
                    "priority": "normal",
                    "requires_ack": True,
                },
            ),
            201,
        )
        _require(
            client.post(
                f"/api/v1/messages/{completed_task['message_id']}/reply",
                headers=_agent_headers(research, "demo-task-result"),
                json={
                    "type": "result",
                    "subject": "报告目录检查完成",
                    "content": {
                        "format": "json",
                        "body": {
                            "summary": "目录完整，建议补充风险边界",
                            "status": "completed",
                            "next_steps": ["补充风险边界", "保留来源日期"],
                            "evidence": {
                                "checked_sections": ["结论", "证据", "风险"],
                                "coverage": 1.0,
                            },
                        },
                    },
                    "result": {"status": "completed", "summary": "目录完整，建议补充风险边界"},
                    "priority": "normal",
                },
            ),
            201,
        )
        pdf_attachment = _require(
            client.post(
                "/api/v1/attachments",
                headers=_agent_headers(research),
                files={"file": ("研究摘要.pdf", _demo_pdf(), "application/pdf")},
            ),
            201,
        )
        html_attachment = _require(
            client.post(
                "/api/v1/attachments",
                headers=_agent_headers(research),
                files={
                    "file": (
                        "来源概览.html",
                        (
                            "<!doctype html><meta charset='utf-8'>"
                            "<style>body{font:16px system-ui;padding:28px;color:#17324d}"
                            "h1{color:#0b807c}li{margin:10px 0}</style>"
                            "<h1>来源概览</h1><ul><li>资料 A：公开报告</li>"
                            "<li>资料 B：机构公告</li></ul>"
                            "<script>document.body.dataset.scriptRan='true'</script>"
                        ).encode(),
                        "text/html",
                    )
                },
            ),
            201,
        )
        update = _require(
            client.post(
                "/api/v1/messages",
                headers=_agent_headers(research, "demo-research-update"),
                json={
                    "to": [{"address": personal["agent"]["address"]}],
                    "type": "message",
                    "subject": "研究资料已准备",
                    "content": {"format": "text", "body": "两份公开资料已经完成交叉核对。"},
                    "attachments": [pdf_attachment["id"], html_attachment["id"]],
                    "priority": "normal",
                    "requires_ack": True,
                },
            ),
            201,
        )
        _require(
            client.post(
                f"/api/v1/messages/{update['message_id']}/ack",
                headers=_agent_headers(personal),
            ),
            200,
        )
        _require(
            client.post(
                f"/api/v1/messages/{update['message_id']}/reply",
                headers=_agent_headers(personal, "demo-research-update-reply"),
                json={
                    "type": "response",
                    "subject": "研究资料核对回复",
                    "content": {
                        "format": "text",
                        "body": "收到，请在摘要中保留来源日期和适用范围。",
                    },
                    "priority": "normal",
                    "requires_ack": True,
                },
            ),
            201,
        )
        organization_message = _require(
            client.post(
                f"/api/v1/organizations/{organization['organization']['id']}/channel/messages",
                headers=_agent_headers(personal, "demo-organization-channel-task"),
                json={
                    "type": "task",
                    "subject": "本周研究结论协作",
                    "content": {
                        "format": "text",
                        "body": "请结合已有核对结果，给出本周研究结论和下一步。",
                    },
                    "task": {
                        "instruction": "整理本周研究结论和下一步",
                        "expected_output": "三条结论与负责人建议",
                    },
                    "requested_responder_agent_ids": [research["agent"]["id"]],
                },
            ),
            201,
        )
        _require(
            client.post(
                f"/api/v1/organizations/{organization['organization']['id']}/channel/messages",
                headers=_agent_headers(research, "demo-organization-channel-result"),
                json={
                    "type": "result",
                    "subject": "本周研究结论已整理",
                    "content": {
                        "format": "json",
                        "body": {
                            "summary": "结论、来源边界和下一步均已整理",
                            "status": "completed",
                            "next_steps": ["由北辰助理确认发布范围"],
                        },
                    },
                    "result": {
                        "status": "completed",
                        "summary": "结论、来源边界和下一步均已整理",
                    },
                    "thread_id": organization_message["thread_id"],
                    "reply_to_event_id": organization_message["event_id"],
                    "requested_responder_agent_ids": [personal["agent"]["id"]],
                },
            ),
            201,
        )
        _require(
            client.post(
                "/api/v1/approval-requests",
                headers=_agent_headers(personal, "demo-approval"),
                json={
                    "action_type": "publish.report",
                    "summary": "允许向组织成员发布研究摘要",
                    "justification": "摘要已完成来源核对，需要 Human 明确授权后继续。",
                    "risk_level": "medium",
                    "payload": {"report_id": "local-demo-report", "audience": "organization"},
                },
            ),
            201,
        )

        with database.session_factory() as session:
            now = datetime.now(UTC)
            personal_agent = session.get(Agent, UUID(personal["agent"]["id"]))
            research_agent = session.get(Agent, UUID(research["agent"]["id"]))
            waiting_agent = session.get(Agent, UUID(waiting["agent"]["id"]))
            if personal_agent is None or research_agent is None or waiting_agent is None:
                raise RuntimeError("demo Agents were not persisted")
            personal_agent.last_seen_at = now
            research_agent.last_seen_at = now - timedelta(minutes=3)
            waiting_agent.last_seen_at = None
            current = ConnectorInstance(
                connector_id="demo-codex-current",
                agent_id=personal_agent.id,
                human_user_id=UUID(human_id),
                connector_type="codex",
                display_name="这台 Mac 上的 Codex",
                device_name="当前设备",
                client_version="agentpost-connect/0.1.33",
                status="active",
                health_status="healthy",
                created_at=now - timedelta(days=2),
                activated_at=now - timedelta(days=2),
                last_seen_at=now,
                last_heartbeat_at=now,
            )
            historical = ConnectorInstance(
                connector_id="demo-codex-history",
                agent_id=personal_agent.id,
                human_user_id=UUID(human_id),
                connector_type="codex",
                display_name="过去使用的 Codex",
                device_name="历史设备",
                client_version="agentpost-connect/0.1.10",
                status="replaced",
                health_status="unknown",
                created_at=now - timedelta(days=9),
                activated_at=now - timedelta(days=9),
                last_seen_at=now - timedelta(days=3),
            )
            awaiting = ConnectorInstance(
                connector_id="demo-workbuddy-awaiting",
                agent_id=waiting_agent.id,
                human_user_id=UUID(human_id),
                connector_type="workbuddy",
                display_name="这台 Mac 上的 WorkBuddy",
                device_name="等待完成设置",
                client_version="agentpost-connect/0.1.33",
                status="active",
                health_status="unknown",
                created_at=now - timedelta(minutes=8),
                activated_at=now - timedelta(minutes=8),
                last_seen_at=None,
                last_heartbeat_at=None,
            )
            session.add_all([current, historical, awaiting])
            session.flush()
            session.add_all(
                [
                    AgentConnectorBinding(
                        agent_id=personal_agent.id,
                        connector_instance_id=current.id,
                        bound_at=now - timedelta(days=2),
                    ),
                    AgentConnectorBinding(
                        agent_id=waiting_agent.id,
                        connector_instance_id=awaiting.id,
                        bound_at=now - timedelta(minutes=8),
                    ),
                ]
            )
            session.commit()

        if not pending_task["message_id"]:
            raise RuntimeError("pending task was not persisted")


def _settings(data_dir: Path, port: int) -> Settings:
    return Settings(
        environment="test",
        database_url=f"sqlite+pysqlite:///{data_dir / 'orbit-demo.db'}",
        storage_path=data_dir / "attachments",
        api_key_pepper="local-demo-agent-pepper",
        human_api_key_pepper="local-demo-human-pepper",
        cursor_secret="local-demo-cursor-secret",
        pairing_secret="local-demo-pairing-secret",
        human_auth_secret="local-demo-human-auth-secret",
        human_mfa_encryption_key="local-demo-human-mfa-key",
        oauth_token_pepper="local-demo-oauth-pepper",
        rate_limit_secret="local-demo-rate-limit-secret",
        registration_token=REGISTRATION_TOKEN,
        admin_token=ADMIN_TOKEN,
        pairing_enabled=True,
        human_self_service_enabled=True,
        open_registration_enabled=True,
        email_delivery_mode="test",
        rate_limit_enabled=False,
        public_base_url=f"http://127.0.0.1:{port}",
        connector_release_version="0.1.33",
        connector_wheel_url="https://agentpost.me/downloads/agentpost-0.1.33-py3-none-any.whl",
        connector_wheel_sha256="5fc73121ec6cca641649194ca2a040a033c9da80d59b62e0fbc9a607b68ed6a9",
        log_level="WARNING",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an isolated local 星云驿 UI demo")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-dir", type=Path)
    args = parser.parse_args()

    if args.host not in {"127.0.0.1", "localhost"}:
        raise SystemExit("The review demo may bind only to localhost")
    if not 1 <= args.port <= 65535:
        raise SystemExit("--port must be between 1 and 65535")

    if args.data_dir is None:
        data_dir = Path(tempfile.mkdtemp(prefix="agentpost-orbit-demo-"))
    else:
        data_dir = args.data_dir.expanduser().resolve()
        data_dir.mkdir(parents=True, exist_ok=True)
        if (data_dir / "orbit-demo.db").exists():
            raise SystemExit("Refusing to overwrite an existing orbit-demo.db")

    settings = _settings(data_dir, args.port)
    _seed(settings)
    runtime_database = Database(settings.database_url)
    app = create_app(settings=settings, database=runtime_database)

    print("\n星云驿本地体验页已准备：")
    print(f"  地址：http://127.0.0.1:{args.port}/orbit")
    print(f"  邮箱：{DEMO_EMAIL}")
    print(f"  密码：{DEMO_PASSWORD}")
    print(f"  临时数据：{data_dir}")
    print("  仅绑定本机；不会连接或修改阿里云数据。按 Ctrl+C 停止。\n")
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
