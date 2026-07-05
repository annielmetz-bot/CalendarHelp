"""Build (and gather data for) the weekly review digest.

`build_html` is pure and unit-tested. `gather` does the Gmail reads.

The digest answers two questions every week:
  1. What unknown senders are sitting in REVIEW, waiting for your call?
  2. What got archived as retail this week (so nothing acts behind your back)?
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from email.utils import parseaddr

from .gmail_client import LABEL_RETAIL, LABEL_REVIEW, GmailClient

DIGEST_LOOKBACK_DAYS = 7
# Cap how many archived messages we fetch details for — a weekly courtesy count.
_ARCHIVED_DETAIL_CAP = 300


@dataclass(frozen=True)
class ReviewItem:
    email: str
    name: str
    subject: str
    count: int  # how many from this sender are in the review pile


def gather(client: GmailClient, days: int = DIGEST_LOOKBACK_DAYS):
    """Return (review_items, archived_by_domain) for the digest."""
    # The REVIEW pile currently held in the inbox.
    review_by_sender: dict[str, ReviewItem] = {}
    for mid in client.search_ids(f'in:inbox label:"{LABEL_REVIEW}"'):
        h = client.get_header_summary(mid, ("From", "Subject"))
        name, addr = parseaddr(h.get("from", ""))
        addr = addr.lower()
        prev = review_by_sender.get(addr)
        if prev is None:
            review_by_sender[addr] = ReviewItem(addr, name, h.get("subject", ""), 1)
        else:
            review_by_sender[addr] = ReviewItem(prev.email, prev.name, prev.subject, prev.count + 1)

    # What was archived as retail in the window.
    archived: Counter[str] = Counter()
    archived_ids = client.search_ids(f'label:"{LABEL_RETAIL}" newer_than:{days}d')
    for mid in archived_ids[:_ARCHIVED_DETAIL_CAP]:
        h = client.get_header_summary(mid, ("From",))
        _, addr = parseaddr(h.get("from", ""))
        domain = addr.split("@")[-1].lower() if "@" in addr else (addr or "unknown")
        archived[domain] += 1

    review_items = sorted(
        review_by_sender.values(), key=lambda r: (-r.count, r.email)
    )
    return review_items, archived, len(archived_ids)


def _esc(s: str) -> str:
    return (
        s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def build_html(
    account: str,
    review_items: list[ReviewItem],
    archived_by_domain: Counter,
    archived_total: int,
    days: int = DIGEST_LOOKBACK_DAYS,
) -> str:
    """Render the digest email body. Pure — no network."""
    n_review = len(review_items)
    rows = ""
    for r in review_items:
        who = _esc(r.name or r.email)
        extra = f" &times;{r.count}" if r.count > 1 else ""
        rows += (
            f'<tr><td style="padding:6px 10px;border-bottom:1px solid #eee;">'
            f'<b>{who}</b>{extra}<br>'
            f'<span style="color:#666;font-size:12px;">{_esc(r.email)}</span></td>'
            f'<td style="padding:6px 10px;border-bottom:1px solid #eee;color:#444;">'
            f'{_esc(r.subject)}</td></tr>'
        )
    if not rows:
        rows = (
            '<tr><td colspan="2" style="padding:10px;color:#666;">'
            "Nothing new to review — inbox is tidy. 🌱</td></tr>"
        )

    top_archived = archived_by_domain.most_common(10)
    archived_rows = "".join(
        f'<li>{_esc(dom)} &mdash; {cnt}</li>' for dom, cnt in top_archived
    ) or "<li>Nothing archived this week.</li>"

    return f"""\
<div style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
            max-width:640px;margin:0 auto;color:#222;">
  <h2 style="margin:0 0 4px;">🌱 Inbox Gardener — weekly review</h2>
  <p style="color:#666;margin:0 0 16px;">{_esc(account)} · last {days} days</p>

  <h3 style="margin:18px 0 6px;">Review pile — {n_review} new sender(s)</h3>
  <p style="color:#666;margin:0 0 8px;font-size:13px;">
    Unknown senders held in your inbox. Tell the Gardener
    <i>&ldquo;keep &lt;sender&gt;&rdquo;</i> or <i>&ldquo;retail &lt;sender&gt;&rdquo;</i>
    and it learns for next time.</p>
  <table style="width:100%;border-collapse:collapse;font-size:14px;">{rows}</table>

  <h3 style="margin:22px 0 6px;">Archived as retail — {archived_total} email(s)</h3>
  <ul style="color:#444;font-size:14px;margin:0;">{archived_rows}</ul>

  <p style="color:#999;font-size:12px;margin-top:22px;">
    Retail mail is archived (removed from the inbox), never deleted &mdash;
    find it any time under the <b>Gardener/Retail</b> label or in All Mail.</p>
</div>"""
