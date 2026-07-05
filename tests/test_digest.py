"""Tests for the pure digest HTML builder."""

from collections import Counter

from gardener.digest import ReviewItem, build_html


def test_digest_lists_review_senders_and_counts():
    items = [
        ReviewItem("info@pesieducation.com", "PESI", "New CE course", 3),
        ReviewItem("reply@nextdoor.com", "Nextdoor", "Your neighborhood", 1),
    ]
    html = build_html("annielmetz@gmail.com", items, Counter(), 0)
    assert "2 new sender(s)" in html
    assert "PESI" in html
    assert "info@pesieducation.com" in html
    assert "&times;3" in html          # count shown for repeat sender
    assert "New CE course" in html


def test_digest_shows_archived_summary():
    archived = Counter({"lululemon.com": 4, "poshmark.com": 2})
    html = build_html("me@gmail.com", [], archived, 6)
    assert "6 email(s)" in html
    assert "lululemon.com &mdash; 4" in html


def test_digest_empty_states_are_friendly():
    html = build_html("me@gmail.com", [], Counter(), 0)
    assert "Nothing new to review" in html
    assert "Nothing archived this week" in html


def test_digest_escapes_html_in_sender_fields():
    items = [ReviewItem("x@evil.com", "<script>alert(1)</script>", "Hi <b>", 1)]
    html = build_html("me@gmail.com", items, Counter(), 0)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
