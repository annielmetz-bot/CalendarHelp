"""Orchestration: turn a batch of messages into decisions, then act on them.

Split in two so the logic is testable:

* `plan()` is pure — messages in, decisions out. No network.
* `execute()` performs the Gmail writes, but honors `dry_run` and takes the
  client as an argument, so a fake client proves the behavior in tests.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .classifier import Bucket, classify
from .gmail_client import GmailClient, Message


@dataclass(frozen=True)
class Decision:
    message: Message
    bucket: Bucket
    reason: str

    @property
    def sender(self) -> str:
        return self.message.meta.from_email or "(no from)"


def plan(
    messages: Iterable[Message],
    keep: list[str],
    retail: list[str],
    learned: dict[str, str],
) -> list[Decision]:
    decisions = []
    for msg in messages:
        c = classify(msg.meta, keep, retail, learned)
        decisions.append(Decision(msg, c.bucket, c.reason))
    return decisions


# Which client action each bucket maps to. KEEP is only marked as processed.
_ACTION = {
    Bucket.RETAIL: "label_and_archive_retail",
    Bucket.REVIEW: "label_review",
    Bucket.KEEP: "mark_processed",
}


def execute(
    client: GmailClient,
    decisions: Iterable[Decision],
    dry_run: bool,
) -> dict[Bucket, int]:
    """Apply each decision. In dry-run, count but touch nothing."""
    counts = {Bucket.KEEP: 0, Bucket.RETAIL: 0, Bucket.REVIEW: 0}
    for d in decisions:
        counts[d.bucket] += 1
        if dry_run:
            continue
        getattr(client, _ACTION[d.bucket])(d.message.id)
    return counts
