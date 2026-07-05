"""Gmail API client — the only module that touches the network.

Design choices that matter:

* **Scope is `gmail.modify`** — label, archive, and send. It deliberately does
  NOT request `https://mail.google.com/`, so this agent physically cannot
  permanently delete mail. The worst it can do is archive (reversible).
* The **pure** helpers (`message_to_meta`, `build_raw_message`) carry no Google
  imports, so they are unit-tested without credentials. The Google libraries are
  imported lazily inside the methods that need them.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from email.mime.text import MIMEText
from email.utils import parseaddr

from .classifier import EmailMeta

# Only modify — never the full-access scope. No permanent delete, by construction.
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

# Headers the classifier actually reads. We fetch only these (format=metadata).
METADATA_HEADERS = ["From", "List-Id", "List-Unsubscribe", "Precedence"]

# Gmail label names the agent owns.
LABEL_RETAIL = "Gardener/Retail"
LABEL_REVIEW = "Gardener/Review"
LABEL_PROCESSED = "Gardener/Processed"


@dataclass(frozen=True)
class Message:
    """A fetched message: its Gmail id plus the metadata we classify on."""

    id: str
    meta: EmailMeta


# --------------------------------------------------------------------------- #
# Pure helpers (no network, no Google imports) — these are unit-tested.
# --------------------------------------------------------------------------- #

def message_to_meta(msg: dict) -> Message:
    """Convert a Gmail `format=metadata` message dict into our Message."""
    payload = msg.get("payload", {}) or {}
    headers = {
        (h.get("name") or "").lower(): (h.get("value") or "")
        for h in payload.get("headers", [])
    }
    name, addr = parseaddr(headers.get("from", ""))
    classify_headers = {
        k: headers[k]
        for k in ("list-id", "list-unsubscribe", "precedence")
        if k in headers
    }
    meta = EmailMeta(
        from_email=addr,
        from_name=name,
        headers=classify_headers,
        gmail_labels=tuple(msg.get("labelIds", []) or ()),
    )
    return Message(id=msg.get("id", ""), meta=meta)


def build_raw_message(sender: str, to: str, subject: str, html_body: str) -> dict:
    """Build the base64url `{"raw": ...}` body for `users.messages.send`."""
    mime = MIMEText(html_body, "html", "utf-8")
    mime["To"] = to
    mime["From"] = sender
    mime["Subject"] = subject
    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
    return {"raw": raw}


# --------------------------------------------------------------------------- #
# Credentials + service (Google libraries imported lazily).
# --------------------------------------------------------------------------- #

def load_credentials(credentials_path, token_path):
    """Load a stored user token, refreshing it if expired.

    Raises a clear error if no token exists yet — run `authorize.py` once to
    create one. Never launches an interactive flow here (this runs headless).
    """
    from pathlib import Path

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    token_path = Path(token_path)
    raw = token_path.read_text().strip() if token_path.exists() else ""
    if not raw:
        raise SystemExit(
            "Gmail token is missing or empty.\n"
            "  • On GitHub: add repository secrets GMAIL_TOKEN and GMAIL_CREDENTIALS "
            "(Settings → Secrets and variables → Actions). See README → Deploy.\n"
            "  • Locally: run `python authorize.py` once to create token.json."
        )
    try:
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    except ValueError as e:
        raise SystemExit(
            f"Gmail token at {token_path} is malformed ({e}). "
            "Re-create it with `python authorize.py`, or re-paste the full "
            "token.json into the GMAIL_TOKEN secret."
        ) from e
    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json())
    return creds


def build_service(creds):
    from googleapiclient.discovery import build

    return build("gmail", "v1", credentials=creds, cache_discovery=False)


# --------------------------------------------------------------------------- #
# The client.
# --------------------------------------------------------------------------- #

class GmailClient:
    def __init__(self, service, user_id: str = "me"):
        self.service = service
        self.user_id = user_id
        self._label_ids: dict[str, str] = {}

    @classmethod
    def from_settings(cls, settings) -> GmailClient:
        creds = load_credentials(settings.credentials_path, settings.token_path)
        return cls(build_service(creds))

    # ---- reading ----

    def search_ids(self, query: str) -> list[str]:
        """All message ids matching a Gmail search query (paginated)."""
        ids: list[str] = []
        req = self.service.users().messages().list(userId=self.user_id, q=query)
        while req is not None:
            resp = req.execute()
            ids.extend(m["id"] for m in resp.get("messages", []))
            req = self.service.users().messages().list_next(req, resp)
        return ids

    def list_new_message_ids(self, after_epoch: int, exclude_processed: bool = True) -> list[str]:
        """Ids of inbox messages newer than `after_epoch`, oldest work first."""
        query = f"in:inbox after:{after_epoch}"
        if exclude_processed:
            query += f' -label:"{LABEL_PROCESSED}"'
        return self.search_ids(query)

    def get_header_summary(
        self, msg_id: str, headers: tuple[str, ...] = ("From", "Subject")
    ) -> dict:
        """Lowercased header values for one message — used to build the digest."""
        msg = (
            self.service.users()
            .messages()
            .get(userId=self.user_id, id=msg_id, format="metadata", metadataHeaders=list(headers))
            .execute()
        )
        payload = msg.get("payload", {}) or {}
        return {
            (h.get("name") or "").lower(): (h.get("value") or "")
            for h in payload.get("headers", [])
        }

    def get_message(self, msg_id: str) -> Message:
        msg = (
            self.service.users()
            .messages()
            .get(
                userId=self.user_id,
                id=msg_id,
                format="metadata",
                metadataHeaders=METADATA_HEADERS,
            )
            .execute()
        )
        return message_to_meta(msg)

    # ---- labels ----

    def get_or_create_label(self, name: str) -> str:
        if name in self._label_ids:
            return self._label_ids[name]
        existing = self.service.users().labels().list(userId=self.user_id).execute()
        for lbl in existing.get("labels", []):
            if lbl["name"] == name:
                self._label_ids[name] = lbl["id"]
                return lbl["id"]
        created = (
            self.service.users()
            .labels()
            .create(
                userId=self.user_id,
                body={
                    "name": name,
                    "labelListVisibility": "labelShow",
                    "messageListVisibility": "show",
                },
            )
            .execute()
        )
        self._label_ids[name] = created["id"]
        return created["id"]

    def _modify(self, msg_id: str, add: list[str] | None = None, remove: list[str] | None = None):
        body = {"addLabelIds": add or [], "removeLabelIds": remove or []}
        return (
            self.service.users()
            .messages()
            .modify(userId=self.user_id, id=msg_id, body=body)
            .execute()
        )

    def label_and_archive_retail(self, msg_id: str) -> None:
        """Apply the Retail label and remove from the inbox (archive)."""
        retail = self.get_or_create_label(LABEL_RETAIL)
        processed = self.get_or_create_label(LABEL_PROCESSED)
        self._modify(msg_id, add=[retail, processed], remove=["INBOX"])

    def label_review(self, msg_id: str) -> None:
        """Tag as Review but leave it in the inbox."""
        review = self.get_or_create_label(LABEL_REVIEW)
        processed = self.get_or_create_label(LABEL_PROCESSED)
        self._modify(msg_id, add=[review, processed])

    def trash_message(self, msg_id: str) -> None:
        """Move to Trash (leaves inbox; auto-purges in ~30 days, recoverable)."""
        self.service.users().messages().trash(userId=self.user_id, id=msg_id).execute()

    def mark_processed(self, msg_id: str) -> None:
        """Used for KEEP: record we've seen it, change nothing else."""
        processed = self.get_or_create_label(LABEL_PROCESSED)
        self._modify(msg_id, add=[processed])

    # ---- sending ----

    def send_html(self, to: str, subject: str, html_body: str, sender: str | None = None) -> str:
        body = build_raw_message(sender or to, to, subject, html_body)
        sent = (
            self.service.users()
            .messages()
            .send(userId=self.user_id, body=body)
            .execute()
        )
        return sent.get("id", "")
