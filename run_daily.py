"""Daily pass: classify new inbox mail and (unless dry-run) file it.

Safe by default: `Settings` defaults `dry_run=True`, so this prints what it
*would* do and changes nothing until you set GARDENER_DRY_RUN=false.

    python run_daily.py            # dry-run report
    GARDENER_DRY_RUN=false python run_daily.py   # actually act

Dry-run never advances the run window or marks messages processed, so you can
re-run it as many times as you like while tuning the rules.
"""

from __future__ import annotations

import os

from gardener.classifier import Bucket
from gardener.config import Settings, load_rules
from gardener.gmail_client import GmailClient
from gardener.runner import execute, plan
from gardener.store import LearnedStore, RunState


def main() -> int:
    settings = Settings.from_env()
    rules = load_rules()
    learned = LearnedStore(settings.learned_path).as_dict()
    state = RunState(settings.state_path)

    client = GmailClient.from_settings(settings)
    # A generous default window; the Gardener/Processed label makes overlap
    # harmless, so a late run never misses mail and never double-acts.
    lookback = int(os.environ.get("GARDENER_LOOKBACK_HOURS", "48"))
    after = state.daily_query_after_epoch(default_lookback_hours=lookback)

    ids = client.list_new_message_ids(after)
    messages = [client.get_message(mid) for mid in ids]
    decisions = plan(messages, rules.keep, rules.retail, learned)

    mode = "DRY-RUN (no changes)" if settings.dry_run else "LIVE"
    print(f"Inbox Gardener — {mode} — {settings.account}")
    print(f"{len(messages)} new message(s) since last run\n")
    for d in decisions:
        print(f"  [{d.bucket.value:6}] {d.sender:42} {d.reason}")

    counts = execute(client, decisions, dry_run=settings.dry_run)

    if not settings.dry_run:
        state.mark_daily_run()

    print(
        f"\nKEEP={counts[Bucket.KEEP]}  "
        f"RETAIL={counts[Bucket.RETAIL]} (archived)  "
        f"REVIEW={counts[Bucket.REVIEW]} (held in inbox)"
    )
    if settings.dry_run:
        print("Dry-run: nothing was modified. Set GARDENER_DRY_RUN=false to act.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
