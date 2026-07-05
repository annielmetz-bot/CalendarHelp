"""Weekly digest: email yourself the REVIEW pile + what was archived.

    python run_weekly.py           # dry-run: writes digest_preview.html, sends nothing
    GARDENER_DRY_RUN=false python run_weekly.py   # actually email the digest
"""

from __future__ import annotations

from pathlib import Path

from gardener.config import Settings
from gardener.digest import build_html, gather
from gardener.gmail_client import GmailClient
from gardener.store import RunState

PREVIEW = Path("digest_preview.html")


def main() -> int:
    settings = Settings.from_env()
    state = RunState(settings.state_path)
    client = GmailClient.from_settings(settings)

    review_items, archived, archived_total = gather(client)
    html = build_html(settings.account, review_items, archived, archived_total)
    subject = f"🌱 Inbox Gardener — {len(review_items)} to review"

    if settings.dry_run:
        PREVIEW.write_text(html)
        print(
            f"DRY-RUN — wrote {PREVIEW} ({len(review_items)} review senders, "
            f"{archived_total} archived). No email sent."
        )
        return 0

    msg_id = client.send_html(settings.account, subject, html, sender=settings.account)
    state.mark_weekly_run()
    print(f"Sent digest to {settings.account} (message {msg_id}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
