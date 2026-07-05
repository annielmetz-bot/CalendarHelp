"""Unit tests for the classifier — the piece we trust most, so it earns tests."""

from gardener.classifier import Bucket, EmailMeta, classify, is_bulk

KEEP = ["nytimes.com", "maps.org", "vanguard.com", "accounts.google.com"]
RETAIL = ["jcrew.com", "sephora.com"]

PROMO_HEADERS = {"list-unsubscribe": "<https://x/u>", "precedence": "bulk"}


def m(addr, name="", headers=None, labels=()):
    return EmailMeta(addr, name, headers or {}, tuple(labels))


def test_keep_exact_domain():
    c = classify(m("newsletter@nytimes.com"), KEEP, RETAIL)
    assert c.bucket is Bucket.KEEP
    assert c.matched == "nytimes.com"


def test_keep_matches_marketing_subdomain():
    # Suffix match: email.nytimes.com must still be KEEP.
    c = classify(m("no-reply@email.nytimes.com"), KEEP, RETAIL)
    assert c.bucket is Bucket.KEEP


def test_keep_wins_over_promo_headers():
    # A KEEP sender that also carries List-Unsubscribe stays KEEP.
    c = classify(m("digest@maps.org", headers=PROMO_HEADERS), KEEP, RETAIL)
    assert c.bucket is Bucket.KEEP
    assert c.is_bulk is True


def test_retail_domain_archived():
    c = classify(m("sale@jcrew.com", headers=PROMO_HEADERS), KEEP, RETAIL)
    assert c.bucket is Bucket.RETAIL


def test_unknown_sender_goes_to_review_even_if_bulk():
    # The safety property: unknown + very "markety" is still only REVIEW.
    c = classify(m("hi@somebrandnew.com", headers=PROMO_HEADERS), KEEP, RETAIL)
    assert c.bucket is Bucket.REVIEW
    assert c.is_bulk is True


def test_unknown_non_bulk_is_review():
    c = classify(m("someone@randomperson.net"), KEEP, RETAIL)
    assert c.bucket is Bucket.REVIEW
    assert c.is_bulk is False


def test_learned_override_beats_static_rules():
    # Owner tagged a previously-KEEP-looking domain as retail; learning wins.
    learned = {"nytimes.com": "RETAIL"}
    c = classify(m("newsletter@nytimes.com"), KEEP, RETAIL, learned)
    assert c.bucket is Bucket.RETAIL
    assert c.reason == "learned:retail"


def test_learned_can_rescue_a_retail_sender_to_keep():
    learned = {"jcrew.com": "KEEP"}
    c = classify(m("sale@jcrew.com"), KEEP, RETAIL, learned)
    assert c.bucket is Bucket.KEEP


def test_exact_address_pattern():
    # accounts.google.com as a full host still matches security mail.
    c = classify(m("no-reply@accounts.google.com"), KEEP, RETAIL)
    assert c.bucket is Bucket.KEEP


def test_is_bulk_detects_gmail_promotions_category():
    assert is_bulk(m("x@brand.com", labels=["CATEGORY_PROMOTIONS"])) is True
    assert is_bulk(m("x@brand.com")) is False
