#!/usr/bin/env python3
"""Read and acknowledge the current AgentPost inbox once."""

from __future__ import annotations

import argparse
import os

from agentpost import AgentPost


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--limit", type=int, default=50)
    result.add_argument(
        "--reply",
        action="store_true",
        help="send a deterministic response before acknowledging each message",
    )
    return result


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def main() -> int:
    args = parser().parse_args()
    with AgentPost(
        server=os.getenv("AGENTPOST_SERVER", "http://localhost:8000"),
        api_key=required_env("AGENTPOST_API_KEY"),
    ) as client:
        page = client.inbox.unread(limit=args.limit)
        print(f"unread={len(page.items)}")
        for message in page.items:
            print(
                f"message_id={message.message_id} from={message.sender.address} "
                f"type={message.message_type} "
                "content_security=UNTRUSTED_EXTERNAL_AGENT_CONTENT"
            )
            current = message.read()
            if args.reply:
                current.reply(
                    f"Received message {message.message_id}.",
                    type="response",
                    subject="Received",
                    idempotency_key=f"receiver-reply-{message.message_id}",
                )
            current.ack()
            print(f"acked message_id={message.message_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
