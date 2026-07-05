"""Tests for the pure Gmail helpers — parsing and MIME building, no network."""

import base64
from email import message_from_bytes

from gardener.classifier import Bucket, classify
from gardener.gmail_client import build_raw_message, message_to_meta


def _api_message(from_value, extra_headers=None, labels=None):
    headers = [{"name": "From", "value": from_value}]
    for name, value in (extra_headers or {}).items():
        headers.append({"name": name, "value": value})
    return {
        "id": "abc123",
        "labelIds": labels or ["INBOX", "UNREAD"],
        "payload": {"headers": headers},
    }


def test_message_to_meta_parses_name_and_address():
    m = message_to_meta(_api_message("The New York Times <newsletter@nytimes.com>"))
    assert m.id == "abc123"
    assert m.meta.from_email == "newsletter@nytimes.com"
    assert m.meta.from_name == "The New York Times"
    assert m.meta.host == "nytimes.com"


def test_message_to_meta_keeps_only_classify_headers():
    m = message_to_meta(
        _api_message(
            "Sale <sale@jcrew.com>",
            extra_headers={
                "List-Unsubscribe": "<https://x/u>",
                "Precedence": "bulk",
                "Subject": "50% off!",  # irrelevant header must be dropped
            },
        )
    )
    assert set(m.meta.headers) == {"list-unsubscribe", "precedence"}
    assert m.meta.headers["precedence"] == "bulk"


def test_message_to_meta_surfaces_promotions_category():
    m = message_to_meta(
        _api_message("x@brand.com", labels=["INBOX", "CATEGORY_PROMOTIONS"])
    )
    assert "CATEGORY_PROMOTIONS" in m.meta.gmail_labels


def test_meta_flows_into_classifier():
    m = message_to_meta(_api_message("newsletter@email.nytimes.com"))
    c = classify(m.meta, keep=["nytimes.com"], retail=[])
    assert c.bucket is Bucket.KEEP


def test_build_raw_message_is_valid_base64url_with_subject():
    body = build_raw_message(
        "me@gmail.com", "me@gmail.com", "Weekly review", "<p>hi</p>"
    )
    raw = base64.urlsafe_b64decode(body["raw"])
    parsed = message_from_bytes(raw)
    assert parsed["Subject"] == "Weekly review"
    assert parsed["To"] == "me@gmail.com"
    # Body is base64-encoded on the wire (utf-8); decode it back to the HTML.
    assert parsed.get_payload(decode=True).decode() == "<p>hi</p>"
