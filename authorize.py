"""One-time OAuth: turn your downloaded `credentials.json` into a `token.json`.

Run this ONCE on your own machine (it opens a browser to consent):

    pip install -r requirements.txt
    python authorize.py

It reads `credentials.json` (your Desktop-app OAuth client, downloaded from
Google Cloud) and writes `token.json` (the long-lived refresh token the daily
agent uses). Both files are gitignored — never commit them. For scheduled runs,
paste the contents of `token.json` into a repository secret (see DESIGN.md).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

from gardener.gmail_client import SCOPES

CREDENTIALS = Path(os.environ.get("GARDENER_CREDENTIALS", "credentials.json"))
TOKEN = Path(os.environ.get("GARDENER_TOKEN", "token.json"))


def main() -> int:
    if not CREDENTIALS.exists():
        print(
            f"Missing {CREDENTIALS}. Download your OAuth *Desktop app* client "
            "JSON from Google Cloud and save it there first.",
            file=sys.stderr,
        )
        return 1
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS), SCOPES)
    # Opens a browser; falls back to console if no browser is available.
    creds = flow.run_local_server(port=0)
    TOKEN.write_text(creds.to_json())
    print(f"Wrote {TOKEN}. You're authorized — the daily agent can now run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
