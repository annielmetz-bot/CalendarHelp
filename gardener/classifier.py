"""Classify a single email into KEEP / RETAIL / REVIEW.

Pure functions over structured email metadata. No network, no Gmail calls — so
this module is fully unit-testable and is the piece we trust most.

Classification uses only reliable, structured signals (sender domain and a few
headers), never the message body, which the Gmail MCP returns with corrupted
encoding and which is an adversarial signal for marketing mail anyway.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field


class Bucket(str, enum.Enum):
    KEEP = "KEEP"      # never touched; stays in the inbox
    RETAIL = "RETAIL"  # shopping/catalog; labeled + archived out of the inbox
    REVIEW = "REVIEW"  # unknown sender; held in inbox and surfaced weekly


@dataclass(frozen=True)
class EmailMeta:
    """The only fields we classify on. Everything else is deliberately ignored."""

    from_email: str
    from_name: str = ""
    # Header keys are lowercased by the caller.
    headers: dict[str, str] = field(default_factory=dict)
    # Gmail's own system labels, e.g. "CATEGORY_PROMOTIONS".
    gmail_labels: tuple[str, ...] = ()

    @property
    def host(self) -> str:
        """Lowercased host part of the From address (may be a subdomain)."""
        _, _, host = self.from_email.strip().lower().rpartition("@")
        return host


@dataclass(frozen=True)
class Classification:
    bucket: Bucket
    reason: str
    matched: str | None = None  # the rule/pattern that decided it, if any
    is_bulk: bool = False       # looks like a bulk/marketing send (advisory)


def _matches(pattern: str, meta: EmailMeta) -> bool:
    """A pattern with '@' matches the full address; otherwise it is a domain
    suffix, so 'nytimes.com' matches both nytimes.com and email.nytimes.com."""
    pattern = pattern.strip().lower()
    if "@" in pattern:
        return meta.from_email.strip().lower() == pattern
    host = meta.host
    return host == pattern or host.endswith("." + pattern)


def _first_match(patterns: list[str], meta: EmailMeta) -> str | None:
    for p in patterns:
        if _matches(p, meta):
            return p
    return None


def is_bulk(meta: EmailMeta) -> bool:
    """True if headers/labels indicate a bulk marketing send. Advisory only —
    never used to auto-file an unknown sender, only to rank the REVIEW pile."""
    h = meta.headers
    if "list-unsubscribe" in h or "list-id" in h:
        return True
    if h.get("precedence", "").lower() in {"bulk", "list", "junk"}:
        return True
    return "CATEGORY_PROMOTIONS" in meta.gmail_labels


def classify(
    meta: EmailMeta,
    keep: list[str],
    retail: list[str],
    learned: dict[str, str] | None = None,
) -> Classification:
    """Decide the bucket for one email.

    Order: learned corrections win, then the static KEEP list, then RETAIL,
    then everything unknown falls to REVIEW. Unknown senders are *surfaced*,
    never auto-archived — that is what makes the first week safe by construction.
    """
    learned = learned or {}
    bulk = is_bulk(meta)

    # 1. Learned corrections (keyed by domain suffix) win over static rules.
    for domain, bucket_name in learned.items():
        if _matches(domain, meta):
            return Classification(
                Bucket(bucket_name), f"learned:{bucket_name.lower()}", domain, bulk
            )

    # 2. KEEP list — checked before RETAIL so a keep rule always protects.
    if m := _first_match(keep, meta):
        return Classification(Bucket.KEEP, "keep-list", m, bulk)

    # 3. RETAIL list.
    if m := _first_match(retail, meta):
        return Classification(Bucket.RETAIL, "retail-list", m, bulk)

    # 4. Unknown sender → hold for review.
    reason = "unknown-sender (bulk)" if bulk else "unknown-sender"
    return Classification(Bucket.REVIEW, reason, None, bulk)
