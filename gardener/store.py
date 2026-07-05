"""Local persistence: the learned-corrections store and daily/weekly run state.

Both are tiny JSON files. They live outside the repo at runtime (gitignored) so
your sender domains and run history are never committed. All timestamps are
stored as timezone-aware UTC ISO-8601 strings.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from .classifier import Bucket


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _read_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return dict(default)
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        # A corrupt state file must never crash the daily run; fall back clean.
        return dict(default)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
    tmp.replace(path)  # atomic on POSIX — never leaves a half-written file


class LearnedStore:
    """Owner corrections, keyed by sender domain -> "KEEP" | "RETAIL".

    Layered on top of the static YAML rules at classify time, so a correction
    takes effect on the very next run. REVIEW is not a teachable outcome — it is
    only ever the *absence* of a rule.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._data: dict[str, str] = _read_json(self.path, {})

    def teach(self, domain: str, bucket: Bucket | str) -> None:
        bucket = Bucket(bucket)
        if bucket is Bucket.REVIEW:
            raise ValueError("REVIEW is not a teachable bucket; teach KEEP or RETAIL")
        self._data[domain.strip().lower()] = bucket.value
        _write_json(self.path, self._data)

    def forget(self, domain: str) -> None:
        if self._data.pop(domain.strip().lower(), None) is not None:
            _write_json(self.path, self._data)

    def as_dict(self) -> dict[str, str]:
        return dict(self._data)

    def __len__(self) -> int:
        return len(self._data)


class RunState:
    """Tracks the last successful daily and weekly runs.

    The daily runner queries Gmail for mail newer than `last_daily_run`, so the
    agent only ever processes new mail (never the existing backlog).
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._data = _read_json(self.path, {})

    def _get_dt(self, key: str) -> datetime | None:
        raw = self._data.get(key)
        return datetime.fromisoformat(raw) if raw else None

    @property
    def last_daily_run(self) -> datetime | None:
        return self._get_dt("last_daily_run")

    @property
    def last_weekly_run(self) -> datetime | None:
        return self._get_dt("last_weekly_run")

    def daily_query_after_epoch(self, default_lookback_hours: int = 24) -> int:
        """Epoch seconds for a Gmail `after:` filter. On the very first run
        (no prior state) we look back a bounded window, not all of history."""
        last = self.last_daily_run
        if last is None:
            last = _utcnow().timestamp() - default_lookback_hours * 3600
            return int(last)
        return int(last.timestamp())

    def mark_daily_run(self, when: datetime | None = None) -> None:
        self._data["last_daily_run"] = (when or _utcnow()).isoformat()
        _write_json(self.path, self._data)

    def mark_weekly_run(self, when: datetime | None = None) -> None:
        self._data["last_weekly_run"] = (when or _utcnow()).isoformat()
        _write_json(self.path, self._data)
