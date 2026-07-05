"""Load static rules and runtime settings.

Rules come from a human-editable YAML file. Everything operational (dry-run,
where secrets/state live, who the digest goes to) comes from the environment so
nothing sensitive is hard-coded.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RULES = Path(__file__).resolve().parent / "rules.yaml"


@dataclass(frozen=True)
class Rules:
    keep: list[str]
    retail: list[str]
    trash: list[str]


def load_rules(path: str | Path = DEFAULT_RULES) -> Rules:
    data = yaml.safe_load(Path(path).read_text()) or {}
    keep = [str(x).strip().lower() for x in (data.get("keep") or [])]
    retail = [str(x).strip().lower() for x in (data.get("retail") or [])]
    trash = [str(x).strip().lower() for x in (data.get("trash") or [])]
    return Rules(keep=keep, retail=retail, trash=trash)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """Operational settings, all overridable by environment variable."""

    dry_run: bool
    account: str            # the mailbox we tend / send the digest to
    credentials_path: Path  # Google OAuth client secret
    token_path: Path        # stored user token (created on first authorize)
    learned_path: Path
    state_path: Path

    @classmethod
    def from_env(cls) -> Settings:
        state_dir = Path(os.environ.get("GARDENER_STATE_DIR", REPO_ROOT / ".state"))
        return cls(
            # Fail SAFE: default to dry-run. You opt into acting explicitly.
            dry_run=_env_bool("GARDENER_DRY_RUN", True),
            account=os.environ.get("GARDENER_ACCOUNT", "annielmetz@gmail.com"),
            credentials_path=Path(
                os.environ.get("GARDENER_CREDENTIALS", REPO_ROOT / "credentials.json")
            ),
            token_path=Path(os.environ.get("GARDENER_TOKEN", REPO_ROOT / "token.json")),
            learned_path=state_dir / "learned.json",
            state_path=state_dir / "state.json",
        )
