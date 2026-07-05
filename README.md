# Inbox Gardener

A daily agent that keeps `annielmetz@gmail.com` clean. It classifies incoming
mail into **RETAIL** (archive out of the inbox), **KEEP** (leave alone), or
**REVIEW** (unknown sender — hold for a weekly digest), and learns from
corrections over time.

See [`DESIGN.md`](./DESIGN.md) for the full architecture and the decisions
behind it.

## Status

- [x] **Classifier core** — `gardener/classifier.py`, sender/header based, unit-tested.
- [x] **Seed rules** — `gardener/rules.yaml`.
- [x] **Learned store + run state** — `gardener/store.py`, `gardener/config.py`.
- [x] **Gmail client** — `gardener/gmail_client.py` + `authorize.py`, scope `gmail.modify`.
- [x] **Daily runner** — `gardener/runner.py` + `run_daily.py`, dry-run aware.
- [x] **Weekly digest** — `gardener/digest.py` + `run_weekly.py`, self-email.
- [x] **Scheduling** — `.github/workflows/daily.yml` + `weekly.yml`.

## Develop

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest -q
ruff check gardener tests
```

## Run locally

```bash
python authorize.py                 # one-time: creates token.json
python run_daily.py                 # dry-run preview (default, safe)
GARDENER_DRY_RUN=false python run_daily.py    # actually archive/label
python run_weekly.py                # dry-run: writes digest_preview.html
GARDENER_DRY_RUN=false python run_weekly.py   # emails the digest
```

## Deploy (GitHub Actions)

The daily/weekly crons run automatically once two repository **secrets** exist
(Settings → Secrets and variables → Actions → *New repository secret*):

| Secret | Contents |
|---|---|
| `GMAIL_CREDENTIALS` | the full JSON of your `credentials.json` |
| `GMAIL_TOKEN` | the full JSON of your `token.json` |

- **Daily** runs live by default. To preview-only for a while, add a repository
  **variable** `GARDENER_DRY_RUN=true` (or use the *Run workflow* dry-run box).
- Runs are idempotent: every handled message gets a `Gardener/Processed` label,
  so overlapping windows never double-act. No state files to persist.
- Secrets are written to disk only during a run and scrubbed afterward; they are
  never committed (`credentials.json`/`token.json` are gitignored).

### Curated rules vs. learning

`gardener/rules.yaml` is the durable, version-controlled KEEP/RETAIL list. The
runtime `learned.json` layers ad-hoc corrections on top; promote anything you
want to keep permanently into `rules.yaml`.
