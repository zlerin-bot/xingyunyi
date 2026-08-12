#!/usr/bin/env python3
"""Send one AgentPost message or task with the synchronous Python SDK."""

from __future__ import annotations

import argparse
import os

from agentpost import AgentPost


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "--to",
        default=os.getenv("AGENTPOST_TO"),
        help="recipient Agent address (or AGENTPOST_TO)",
    )
    result.add_argument("--subject", default="Hello from AgentPost")
    result.add_argument("--body", default="This message was sent while you could be offline.")
    result.add_argument("--type", choices=("message", "task"), default="message")
    result.add_argument(
        "--idempotency-key",
        help="reuse this exact key when retrying an uncertain send",
    )
    return result


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def main() -> int:
    args = parser().parse_args()
    if not args.to:
        raise SystemExit("--to or AGENTPOST_TO is required")

    task = {"instruction": args.body} if args.type == "task" else None
    with AgentPost(
        server=os.getenv("AGENTPOST_SERVER", "http://localhost:8000"),
        api_key=required_env("AGENTPOST_API_KEY"),
    ) as client:
        message = client.send(
            to=args.to,
            subject=args.subject,
            body=args.body,
            type=args.type,
            task=task,
            idempotency_key=args.idempotency_key,
        )

    print(
        f"accepted message_id={message.message_id} "
        f"status={message.delivery.status} to={message.to[0].address}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
