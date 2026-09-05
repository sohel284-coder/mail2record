"""Pluggable mailbox backends — mirrors the ``AIProvider`` pattern.

Every provider returns the same normalized message shape so the rest of the app
(fetch_emails, the Email/Attachment models, extraction) never cares which
mailbox an email came from:

    {
      "message_id", "sender", "recipient", "subject",
      "body_text", "body_html", "received_at", "source",
      "attachments": [{"filename", "content_type", "size", "content": bytes}],
    }

- ``GmailProvider``  — Gmail API + OAuth token (connected via the web flow).
- ``ImapProvider``   — generic IMAP + app password (Outlook, Yahoo, corporate,
  and Gmail too). This is the "works everywhere, no new code per provider" path.
"""

import email as email_lib
import imaplib
import json
from abc import ABC, abstractmethod
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from . import gmail_client

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# domain -> (imap host, port). Used to pre-fill the IMAP form; always overridable.
IMAP_HOST_PRESETS = {
    "gmail.com": ("imap.gmail.com", 993),
    "googlemail.com": ("imap.gmail.com", 993),
    "outlook.com": ("outlook.office365.com", 993),
    "hotmail.com": ("outlook.office365.com", 993),
    "live.com": ("outlook.office365.com", 993),
    "msn.com": ("outlook.office365.com", 993),
    "office365.com": ("outlook.office365.com", 993),
    "yahoo.com": ("imap.mail.yahoo.com", 993),
    "aol.com": ("imap.aol.com", 993),
    "icloud.com": ("imap.mail.me.com", 993),
    "me.com": ("imap.mail.me.com", 993),
    "fastmail.com": ("imap.fastmail.com", 993),
    "zoho.com": ("imap.zoho.com", 993),
    "gmx.com": ("imap.gmx.com", 993),
    "protonmail.com": ("127.0.0.1", 1143),  # requires the Proton Bridge
}


def guess_imap_host(email_address: str):
    domain = (email_address or "").rsplit("@", 1)[-1].lower()
    return IMAP_HOST_PRESETS.get(domain, (None, 993))


class EmailProvider(ABC):
    def __init__(self, account):
        self.account = account

    @abstractmethod
    def test_connection(self) -> None:
        """Raise on any failure; return None on success."""

    @abstractmethod
    def fetch_new_messages(self, max_results: int = 25) -> list[dict]:
        ...


# --------------------------------------------------------------------------- #
# Gmail
# --------------------------------------------------------------------------- #
class GmailProvider(EmailProvider):
    def _service(self):
        info = dict(self.account.credentials)
        info.setdefault("scopes", GMAIL_SCOPES)
        creds = Credentials.from_authorized_user_info(info, GMAIL_SCOPES)

        if not creds.valid and creds.refresh_token:
            creds.refresh(Request())
            self.account.credentials = json.loads(creds.to_json())
            self.account.save(update_fields=["credentials_encrypted", "updated_at"])

        return build("gmail", "v1", credentials=creds, cache_discovery=False)

    def test_connection(self):
        self._service().users().getProfile(userId="me").execute()

    def fetch_new_messages(self, max_results=25):
        return gmail_client.fetch_new_messages(self._service(), max_results=max_results)


# --------------------------------------------------------------------------- #
# IMAP (Outlook / Yahoo / corporate / anything)
# --------------------------------------------------------------------------- #
class ImapProvider(EmailProvider):
    def __init__(self, account):
        super().__init__(account)
        cfg = account.config or {}
        host, port = guess_imap_host(account.email_address)
        self.host = cfg.get("host") or host
        self.port = int(cfg.get("port") or port or 993)
        self.username = cfg.get("username") or account.email_address
        self.mailbox = cfg.get("mailbox") or "INBOX"
        self.password = (account.credentials or {}).get("password", "")

    def _connect(self):
        if not self.host:
            raise ValueError("No IMAP host configured for this mailbox.")
        conn = imaplib.IMAP4_SSL(self.host, self.port)
        conn.login(self.username, self.password)
        return conn

    def test_connection(self):
        conn = self._connect()
        try:
            conn.select(self.mailbox, readonly=True)
        finally:
            _safe_logout(conn)

    def fetch_new_messages(self, max_results=25):
        conn = self._connect()
        try:
            conn.select(self.mailbox, readonly=True)
            typ, data = conn.search(None, "ALL")
            ids = data[0].split() if data and data[0] else []
            wanted = ids[-max_results:]
            out = []
            for num in reversed(wanted):
                typ, msg_data = conn.fetch(num, "(RFC822)")
                if typ != "OK" or not msg_data or not isinstance(msg_data[0], tuple):
                    continue
                out.append(_parse_imap_message(msg_data[0][1]))
            return out
        finally:
            _safe_logout(conn)


def _safe_logout(conn):
    try:
        conn.logout()
    except Exception:
        pass


def _header_text(raw) -> str:
    if not raw:
        return ""
    try:
        return str(make_header(decode_header(raw)))
    except Exception:
        return str(raw)


def _part_text(part) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        return ""
    return payload.decode(part.get_content_charset() or "utf-8", errors="replace")


def _parse_imap_message(raw_bytes: bytes) -> dict:
    msg = email_lib.message_from_bytes(raw_bytes)

    body_text, body_html = "", ""
    attachments = []
    for part in msg.walk():
        if part.is_multipart():
            continue
        filename = part.get_filename()
        disposition = str(part.get("Content-Disposition") or "").lower()
        if filename or "attachment" in disposition:
            payload = part.get_payload(decode=True) or b""
            attachments.append(
                {
                    "filename": _header_text(filename) or "attachment",
                    "content_type": part.get_content_type(),
                    "size": len(payload),
                    "content": payload,
                }
            )
            continue
        ctype = part.get_content_type()
        if ctype == "text/plain":
            body_text += _part_text(part)
        elif ctype == "text/html":
            body_html += _part_text(part)

    received_at = None
    if msg.get("Date"):
        try:
            received_at = parsedate_to_datetime(msg["Date"])
        except (TypeError, ValueError):
            received_at = None

    message_id = (msg.get("Message-ID") or "").strip()
    if not message_id:
        message_id = f"imap-{abs(hash(raw_bytes))}"

    return {
        "message_id": message_id[:500],
        "sender": _header_text(msg.get("From", "")),
        "recipient": _header_text(msg.get("To", "")),
        "subject": _header_text(msg.get("Subject", "")),
        "body_text": body_text,
        "body_html": body_html,
        "received_at": received_at,
        "source": "imap",
        "attachments": attachments,
    }


# --------------------------------------------------------------------------- #
def get_email_provider(account) -> EmailProvider:
    if account.provider == account.Provider.GMAIL:
        return GmailProvider(account)
    if account.provider == account.Provider.IMAP:
        return ImapProvider(account)
    raise ValueError(f"Unknown email provider: {account.provider!r}")


