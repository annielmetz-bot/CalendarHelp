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
- [ ] Daily runner (dry-run aware)
- [ ] Weekly digest
- [ ] Scheduling (GitHub Actions cron)

## Develop

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest -q
ruff check gardener tests
```
