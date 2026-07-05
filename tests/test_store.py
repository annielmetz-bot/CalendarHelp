"""Tests for the learned store, run state, and config loading."""

from datetime import UTC, datetime, timedelta

import pytest

from gardener.classifier import Bucket, EmailMeta, classify
from gardener.config import load_rules
from gardener.store import LearnedStore, RunState


def test_learned_store_roundtrip(tmp_path):
    p = tmp_path / "learned.json"
    s = LearnedStore(p)
    s.teach("JCrew.com", Bucket.RETAIL)   # normalizes case
    s.teach("mybank.com", "KEEP")         # accepts string too
    # Reload from disk — persistence works.
    assert LearnedStore(p).as_dict() == {"jcrew.com": "RETAIL", "mybank.com": "KEEP"}


def test_learned_store_forget(tmp_path):
    p = tmp_path / "learned.json"
    s = LearnedStore(p)
    s.teach("x.com", Bucket.RETAIL)
    s.forget("X.com")
    assert LearnedStore(p).as_dict() == {}


def test_review_is_not_teachable(tmp_path):
    s = LearnedStore(tmp_path / "learned.json")
    with pytest.raises(ValueError):
        s.teach("x.com", Bucket.REVIEW)


def test_learned_store_feeds_classifier(tmp_path):
    s = LearnedStore(tmp_path / "learned.json")
    s.teach("jcrew.com", Bucket.RETAIL)
    c = classify(EmailMeta("sale@jcrew.com"), keep=[], retail=[], learned=s.as_dict())
    assert c.bucket is Bucket.RETAIL


def test_corrupt_state_file_does_not_crash(tmp_path):
    p = tmp_path / "learned.json"
    p.write_text("{ not valid json")
    assert LearnedStore(p).as_dict() == {}  # falls back clean


def test_run_state_first_run_uses_lookback(tmp_path):
    st = RunState(tmp_path / "state.json")
    assert st.last_daily_run is None
    before = datetime.now(UTC) - timedelta(hours=25)
    # First-run window looks back ~24h, i.e. later than 25h ago.
    assert st.daily_query_after_epoch(default_lookback_hours=24) > before.timestamp()


def test_run_state_persists_last_run(tmp_path):
    p = tmp_path / "state.json"
    when = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)
    st = RunState(p)
    st.mark_daily_run(when)
    # Reload; the query window is now anchored to that timestamp.
    st2 = RunState(p)
    assert st2.last_daily_run == when
    assert st2.daily_query_after_epoch() == int(when.timestamp())


def test_load_rules_seed_has_expected_keep_and_retail():
    rules = load_rules()  # the shipped seed
    assert "nytimes.com" in rules.keep
    assert "maps.org" in rules.keep
    assert "github.com" in rules.keep          # owner's confirmed keep
    assert "lululemon.com" in rules.retail     # seeded retail
    assert "rmpbs.org" in rules.retail         # owner's explicit retail call
