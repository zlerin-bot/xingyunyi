from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from agentpost.config import Settings
from agentpost.messaging.schemas import (
    MAX_CONTENT_BYTES,
    MAX_JSON_DEPTH,
    MAX_METADATA_BYTES,
    MessageType,
)
from agentpost.onboarding.connectivity import heartbeat_timeout_seconds

PROTOCOL_CONTRACT_VERSION = "0.1"


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EndpointContract(ContractModel):
    method: Literal["GET", "POST"]
    path: str
    purpose: str
    changes_state: bool
    bearer_auth_required: bool = True
    required_headers: list[str] = Field(default_factory=list)


class ContentContract(ContractModel):
    native_formats: list[Literal["text", "markdown", "json"]]
    message_types: list[str]
    max_content_bytes: int
    max_metadata_bytes: int
    max_json_depth: int
    max_attachments: int
    max_attachment_bytes: int
    html_is_native_body_format: Literal[False] = False


class StateContract(ContractModel):
    delivery_states: list[Literal["unread", "delivered", "read", "acked"]]
    task_result_states: list[Literal["completed", "partial", "failed", "cancelled"]]
    ack_means_received_not_completed: Literal[True] = True
    direct_reply_handles_task_round: Literal[True] = True
    structured_result_takes_precedence: Literal[True] = True


class HeartbeatContract(ContractModel):
    endpoint: str
    recommended_interval_seconds: int
    offline_after_seconds: int
    online_requires_current_healthy_heartbeat: Literal[True] = True
    never_reported_state: Literal["awaiting_agent"] = "awaiting_agent"
    error_state: Literal["connection_error"] = "connection_error"


class SynchronizationContract(ContractModel):
    source_of_truth: Literal["persistent_inbox"] = "persistent_inbox"
    inbox_endpoint: str
    thread_endpoint_template: str
    cursor_pagination: Literal[True] = True
    maximum_page_size: int
    recommended_poll_interval_seconds: int
    recommended_mode: Literal["poll_with_cursor"] = "poll_with_cursor"
    push_wakeup_available: Literal[False] = False
    human_view_changes_agent_delivery_state: Literal[False] = False


class InteroperabilityContract(ContractModel):
    core_protocol: Literal["agentpost_http_v1"] = "agentpost_http_v1"
    mcp: Literal["adapter"] = "adapter"
    a2a: Literal["mapping_design_only"] = "mapping_design_only"
    a2a_runtime_endpoint: None = None
    smtp_imap: Literal[False] = False


class HumanPresentationContract(ContractModel):
    default_view: Literal["readable_summary"] = "readable_summary"
    raw_agent_data: Literal["available_collapsed"] = "available_collapsed"
    markdown_rendering: Literal["safe_text"] = "safe_text"
    json_rendering: Literal["readable_summary_plus_raw_json"] = "readable_summary_plus_raw_json"
    security_label: Literal["external_agent_content"] = "external_agent_content"
    independent_state_axes: list[str] = Field(
        default_factory=lambda: [
            "human_view",
            "delivery",
            "agent_read",
            "ack",
            "task_result",
        ]
    )


class OrganizationCollaborationContract(ContractModel):
    send_endpoint_template: str
    context_visible_to_all_assigned_agents: Literal[True] = True
    reply_policy: Literal["addressed_agents_reply"] = "addressed_agents_reply"
    private_threads_remain_private: Literal[True] = True
    requested_responder_field: Literal["requested_responder_agent_ids"] = (
        "requested_responder_agent_ids"
    )
    attachment_field: Literal["attachments"] = "attachments"
    attachment_object_shared_across_delivery_copies: Literal[True] = True
    attachments_visible_to_all_assigned_agents: Literal[True] = True


class OnboardingStep(ContractModel):
    order: int
    action: str
    success_evidence: str


class AgentIntegrationContract(ContractModel):
    contract: Literal["AGENTPOST_AGENT_INTEGRATION"] = "AGENTPOST_AGENT_INTEGRATION"
    version: Literal["0.1"] = PROTOCOL_CONTRACT_VERSION
    authentication: Literal["agent_bearer_token_from_os_vault"] = "agent_bearer_token_from_os_vault"
    openapi_url: Literal["/openapi.json"] = "/openapi.json"
    endpoints: list[EndpointContract]
    content: ContentContract
    states: StateContract
    heartbeat: HeartbeatContract
    synchronization: SynchronizationContract
    interoperability: InteroperabilityContract
    human_presentation: HumanPresentationContract
    organization_collaboration: OrganizationCollaborationContract
    onboarding: list[OnboardingStep]


def build_agent_integration_contract(settings: Settings) -> AgentIntegrationContract:
    return AgentIntegrationContract(
        endpoints=[
            EndpointContract(
                method="POST",
                path="/api/v1/messages",
                purpose="send a new message or task",
                changes_state=True,
                required_headers=["Idempotency-Key"],
            ),
            EndpointContract(
                method="GET",
                path="/api/v1/inbox",
                purpose="read the durable Inbox with cursor pagination",
                changes_state=False,
            ),
            EndpointContract(
                method="POST",
                path="/api/v1/messages/{message_id}/reply",
                purpose="reply in the same durable Thread",
                changes_state=True,
                required_headers=["Idempotency-Key"],
            ),
            EndpointContract(
                method="POST",
                path="/api/v1/messages/{message_id}/ack",
                purpose="confirm receipt without claiming task completion",
                changes_state=True,
            ),
            EndpointContract(
                method="POST",
                path="/api/v1/organizations/{organization_id}/channel/messages",
                purpose=(
                    "post organization context to every assigned Agent while naming the Agents "
                    "expected to reply"
                ),
                changes_state=True,
                required_headers=["Idempotency-Key"],
            ),
            EndpointContract(
                method="GET",
                path="/api/v1/organization-channel",
                purpose=(
                    "read the current Agent's single organization and channel participants; "
                    "returns a selection-required conflict when the default Agent participates "
                    "in multiple organizations"
                ),
                changes_state=False,
            ),
            EndpointContract(
                method="GET",
                path="/api/v1/organization-channels",
                purpose=(
                    "list organization channels available to the current Agent, including "
                    "default participation when its Human has not selected another Agent"
                ),
                changes_state=False,
            ),
            EndpointContract(
                method="POST",
                path="/api/v1/attachments",
                purpose="upload an attachment before referencing its identifier",
                changes_state=True,
            ),
            EndpointContract(
                method="POST",
                path="/connect/heartbeat",
                purpose="report health for the current active Connector",
                changes_state=True,
            ),
        ],
        content=ContentContract(
            native_formats=["text", "markdown", "json"],
            message_types=[value.value for value in MessageType],
            max_content_bytes=MAX_CONTENT_BYTES,
            max_metadata_bytes=MAX_METADATA_BYTES,
            max_json_depth=MAX_JSON_DEPTH,
            max_attachments=32,
            max_attachment_bytes=settings.max_attachment_bytes,
        ),
        states=StateContract(
            delivery_states=["unread", "delivered", "read", "acked"],
            task_result_states=["completed", "partial", "failed", "cancelled"],
        ),
        heartbeat=HeartbeatContract(
            endpoint="/connect/heartbeat",
            recommended_interval_seconds=settings.connector_heartbeat_interval_seconds,
            offline_after_seconds=heartbeat_timeout_seconds(
                settings.connector_heartbeat_interval_seconds
            ),
        ),
        synchronization=SynchronizationContract(
            inbox_endpoint="/api/v1/inbox",
            thread_endpoint_template="/api/v1/threads/{thread_id}",
            maximum_page_size=100,
            recommended_poll_interval_seconds=(settings.connector_inbox_poll_interval_seconds),
        ),
        interoperability=InteroperabilityContract(),
        human_presentation=HumanPresentationContract(),
        organization_collaboration=OrganizationCollaborationContract(
            send_endpoint_template=("/api/v1/organizations/{organization_id}/channel/messages")
        ),
        onboarding=[
            OnboardingStep(
                order=1,
                action="fetch and validate this versioned contract",
                success_evidence="contract and version match the server response headers",
            ),
            OnboardingStep(
                order=2,
                action="complete Human-authorized pairing and keep the token in the OS vault",
                success_evidence="the Connector is active without exposing a credential",
            ),
            OnboardingStep(
                order=3,
                action="send a healthy heartbeat and read the Inbox using a cursor",
                success_evidence="heartbeat is accepted and Inbox pagination is repeatable",
            ),
            OnboardingStep(
                order=4,
                action="exchange a task, direct reply, structured result, and attachment",
                success_evidence=(
                    "all items remain in one Thread and preserve their distinct states"
                ),
            ),
        ],
    )
