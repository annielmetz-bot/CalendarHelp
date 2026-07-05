"""Tests for planning and execution, using a fake Gmail client (no network)."""

from gardener.classifier import Bucket, EmailMeta
from gardener.gmail_client import Message
from gardener.runner import Decision, execute, plan


def msg(mid, addr):
    return Message(id=mid, meta=EmailMeta(from_email=addr))


class FakeClient:
    """Records the mutating calls the runner makes."""

    def __init__(self):
        self.calls = []

    def label_and_archive_retail(self, mid):
        self.calls.append(("retail", mid))

    def label_review(self, mid):
        self.calls.append(("review", mid))

    def trash_message(self, mid):
        self.calls.append(("trash", mid))

    def mark_processed(self, mid):
        self.calls.append(("processed", mid))


KEEP = ["nytimes.com"]
RETAIL = ["jcrew.com"]


def test_plan_classifies_each_message():
    messages = [msg("1", "x@nytimes.com"), msg("2", "y@jcrew.com"), msg("3", "z@unknown.io")]
    decisions = plan(messages, KEEP, RETAIL, learned={})
    assert [d.bucket for d in decisions] == [Bucket.KEEP, Bucket.RETAIL, Bucket.REVIEW]
    assert decisions[1].sender == "y@jcrew.com"


def test_execute_dry_run_touches_nothing():
    client = FakeClient()
    decisions = [Decision(msg("2", "y@jcrew.com"), Bucket.RETAIL, "retail-list")]
    counts = execute(client, decisions, dry_run=True)
    assert client.calls == []                 # nothing mutated
    assert counts[Bucket.RETAIL] == 1         # but still counted for the report


def test_execute_live_routes_each_bucket_to_its_action():
    client = FakeClient()
    decisions = [
        Decision(msg("1", "x@nytimes.com"), Bucket.KEEP, "keep-list"),
        Decision(msg("2", "y@jcrew.com"), Bucket.RETAIL, "retail-list"),
        Decision(msg("3", "z@unknown.io"), Bucket.REVIEW, "unknown-sender"),
        Decision(msg("4", "a@nextdoor.com"), Bucket.TRASH, "trash-list"),
    ]
    counts = execute(client, decisions, dry_run=False)
    assert client.calls == [
        ("processed", "1"),
        ("retail", "2"),
        ("review", "3"),
        ("trash", "4"),
    ]
    assert counts == {Bucket.KEEP: 1, Bucket.RETAIL: 1, Bucket.TRASH: 1, Bucket.REVIEW: 1}


def test_plan_routes_trash_list_ahead_of_retail():
    # A domain on both lists is trashed, not archived; keep still wins over trash.
    decisions = plan(
        [msg("1", "a@nextdoor.com"), msg("2", "b@nytimes.com")],
        keep=["nytimes.com"],
        retail=["nextdoor.com"],
        learned={},
        trash=["nextdoor.com"],
    )
    assert decisions[0].bucket is Bucket.TRASH
    assert decisions[1].bucket is Bucket.KEEP
