# Inbox Gardener — Design

A daily agent that keeps `annielmetz@gmail.com` clean by classifying incoming
mail and archiving retail/promotional clutter, while never touching the things
that matter.

## Decisions (locked with the owner)

| Decision | Choice |
|---|---|
| Execution | **Standalone Python script + its own write-scoped Gmail OAuth token.** Not the Gmail MCP — a headless MCP session came back read-only, which is the whole reason a dedicated OAuth token exists. |
| Retail action | **Label `Gardener/Retail` + archive** (remove from `INBOX`). Reversible — archived, never deleted. **Dry-run for the first week.** |
| Weekly review | **Self-email digest** to `annielmetz@gmail.com`: the REVIEW pile, newly detected subscriptions, and what was archived. |
| Daily scope | **New mail only** (`newer_than` the last successful run). The existing backlog is left untouched. |
| Home | Its own repo, **separate from Bill Pop**. |

## The three buckets

- **KEEP** — never touched. Stays in the inbox. (NYT, Medscape, local NM news,
  StoryWorth, counselor-ed job alerts, every psychedelic-field newsletter, and
  anything financial/transactional.)
- **RETAIL** — shopping/catalog senders. Labeled + archived out of the inbox.
- **REVIEW** — an unknown sender we have no rule for yet. Left in the inbox,
  labeled `Gardener/Review`, and surfaced in the weekly digest so lists can
  never silently pile up.

## Why classify by sender, not body

The Gmail MCP returned corrupted body encoding, and even via the raw API,
promotional HTML bodies are a poor, adversarial signal. So classification uses
only structured, reliable fields:

- **Sender domain** (the org domain / eTLD+1 of the `From:` address, plus
  common marketing subdomains like `email.brand.com`).
- **Headers**: `List-Id`, `List-Unsubscribe`, `Precedence: bulk`, and Gmail's
  own category labels (`CATEGORY_PROMOTIONS`) — used to recognize *that*
  something is a bulk/marketing send, never to auto-file an unknown sender.

## Classification order (deterministic, then learned)

1. **Learned overrides** (owner corrections) win over everything.
2. **KEEP list** match → `KEEP`.
3. **RETAIL list** match → `RETAIL`.
4. Otherwise → `REVIEW` (unknown sender), regardless of how "markety" it looks.
   Unknown senders are *surfaced*, never auto-archived. Retail rules grow from
   corrections during the dry-run week and beyond.

This makes the first week safe by construction: with an empty retail list,
nothing gets archived — everything unknown lands in the REVIEW digest, you
tag the true retail senders, and the agent learns them.

## Learning loop

- Corrections are captured two ways: (a) a sender you move/tag manually, and
  (b) the weekly digest offering one-tap "this is retail / this is keep"
  affordances. Both write to a `learned.json` store keyed by sender domain.
- The learned store is layered on top of the static YAML rules at classify
  time, so corrections take effect on the very next run.

## Components (build order)

1. **`classifier.py`** — pure functions over email metadata. Fully unit-tested,
   no network. *(this stage)*
2. **`rules.yaml`** — human-editable KEEP/RETAIL seed lists.
3. **`store.py`** — `learned.json` + last-run state (idempotency / dedupe).
4. **`gmail_client.py`** — OAuth + Gmail API: list new messages, read headers,
   apply labels, archive, send the digest.
5. **`run_daily.py`** — orchestrates a daily pass (dry-run aware).
6. **`run_weekly.py`** — builds and sends the review digest.
7. **Scheduling** — GitHub Actions cron (daily + weekly), token in repo secrets.

## Safety properties

- **Reversible**: RETAIL is archive-only. Recoverable from All Mail / the label.
- **Fail-safe default**: unknown → REVIEW, never archive.
- **Dry-run**: first week logs intended actions without executing them.
- **Idempotent**: each message is processed once (tracked by message id + a
  `Gardener/Processed` label), so re-runs never double-act.
- **Least privilege**: OAuth scope is `gmail.modify` (label/archive/send) — not
  full `https://mail.google.com/` (no permanent delete).
