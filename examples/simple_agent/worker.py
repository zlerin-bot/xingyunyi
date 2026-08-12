#!/usr/bin/env python3
"""Run a deterministic, provider-free AgentPost inbox worker."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from agentpost_sdk import AgentPostError, Message, ResponseError

from agentpost import AgentPost

SUPPORTED_TYPES = {"message", "task"}


@dataclass
class CycleResult:
    processed: int = 0
    failed: int = 0


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def nonnegative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return parsed


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "--once",
        action="store_true",
        help="process the current queue once and exit",
    )
    result.add_argument(
        "--poll-seconds",
        type=nonnegative_float,
        default=float(os.getenv("AGENTPOST_POLL_SECONDS", "30")),
    )
    result.add_argument("--limit", type=positive_int, default=50)
    return result


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def content_fingerprint(body: Any) -> str:
    """Fingerprint untrusted content without interpreting or executing it."""

    encoded = json.dumps(
        body,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class DeterministicWorker:
    def __init__(self, client: AgentPost, *, limit: int) -> None:
        self.client = client
        self.limit = limit

    def _messages(self, status: str) -> Iterator[Message]:
        cursor: str | None = None
        seen_cursors: set[str] = set()
        while True:
            page = self.client.inbox.list(status=status, limit=self.limit, cursor=cursor)
            yield from page.items
            if not page.has_more or page.next_cursor is None:
                return
            if page.next_cursor in seen_cursors:
                raise RuntimeError("server repeated an inbox cursor")
            seen_cursors.add(page.next_cursor)
            cursor = page.next_cursor

    @staticmethod
    def _reply(message: Message) -> None:
        fingerprint = content_fingerprint(message.content.body)
        idempotency_key = f"simple-agent-reply-{message.message_id}"
        if message.message_type == "task":
            message.reply(
                (
                    "Deterministic processing recorded the external task content "
                    f"with SHA-256 {fingerprint}."
                ),
                type="result",
                subject="Deterministic task result",
                result={
                    "status": "partial",
                    "summary": (
                        "The provider-free example fingerprints input but intentionally "
                        "does not execute arbitrary task instructions."
                    ),
                },
                idempotency_key=idempotency_key,
            )
        else:
            message.reply(
                f"Received message {message.message_id}; content SHA-256 is {fingerprint}.",
                type="response",
                subject="Deterministic receipt",
                idempotency_key=idempotency_key,
            )

    def _process(self, message: Message) -> None:
        print(
            f"received message_id={message.message_id} from={message.sender.address} "
            f"type={message.message_type} "
            "security=UNTRUSTED_EXTERNAL_AGENT_CONTENT"
        )
        # The body is data, never a system instruction. This worker grants it no tools.
        current = message
        if message.delivery.status == "delivered":
            current = message.read()
        self._reply(current)
        current.ack()
        print(f"processed_and_acked message_id={message.message_id}")

    def cycle(self) -> CycleResult:
        result = CycleResult()
        # Include read-but-unacked messages so a failure after read is recoverable.
        for status in ("unread", "read"):
            for message in self._messages(status):
                if message.message_type not in SUPPORTED_TYPES:
                    continue
                try:
                    self._process(message)
                except AgentPostError as exc:
                    result.failed += 1
                    code = exc.code if isinstance(exc, ResponseError) else type(exc).__name__
                    print(f"processing_failed message_id={message.message_id} code={code}")
                else:
                    result.processed += 1
        return result


def main() -> int:
    args = parser().parse_args()
    with AgentPost(
        server=os.getenv("AGENTPOST_SERVER", "http://localhost:8000"),
        api_key=required_env("AGENTPOST_API_KEY"),
    ) as client:
        worker = DeterministicWorker(client, limit=args.limit)
        while True:
            try:
                result = worker.cycle()
            except AgentPostError as exc:
                code = exc.code if isinstance(exc, ResponseError) else type(exc).__name__
                print(f"poll_failed code={code}")
                if args.once:
                    return 1
            else:
                print(f"cycle_complete processed={result.processed} failed={result.failed}")
                if args.once:
                    return 1 if result.failed else 0
            time.sleep(args.poll_seconds)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("stopped")
