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
                    "display_name": "本地体验用户",
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
        _require(
            client.put(
                f"/api/v1/admin/humans/{human_id}/agents/{personal['agent']['id']}",
                headers=admin_headers,
                json={"role": "owner"},
            ),
            200,
        )
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
                    "slug": "demo-research",
                    "name": "本地演示研究组",
                    "description": "仅存在于本机临时数据库，用于体验组织授权边界。",
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
                    "content": {"format": "markdown", "body": "目录完整，建议补充一页风险边界。"},
                    "result": {"status": "completed", "summary": "目录完整，建议补充风险边界"},
                    "priority": "normal",
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
                device_name="本地演示设备",
                client_version="agentpost-connect/0.1.12",
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
                device_name="旧演示设备",
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
                client_version="agentpost-connect/0.1.12",
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
        connector_release_version="0.1.12",
        connector_wheel_url="https://agentpost.me/downloads/agentpost-0.1.12-py3-none-any.whl",
        connector_wheel_sha256="abec6302203964eae51312adebaa509ccce228cf0342d9c4f86b0e9db7f5d821",
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
