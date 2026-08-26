"""Thin wrapper around the Gmail API for fetching new messages."""

import base64
import os
from email.utils import parsedate_to_datetime

from django.conf import settings
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

CREDENTIALS_DIR = os.path.join(settings.BASE_DIR, "credentials")
CLIENT_SECRET_FILE = os.path.join(CREDENTIALS_DIR, "gmail_credentials.json")
TOKEN_FILE = os.path.join(CREDENTIALS_DIR, "gmail_token.json")


def get_gmail_service():
    """
    Returns an authenticated Gmail API service object.
    First run opens a browser for the OAuth consent screen; afterwards
    a refresh token is cached in TOKEN_FILE so this runs headless.
    """
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def fetch_new_messages(service, max_results=25):
    """
    Fetches recent messages from the inbox. Returns a list of dicts with
    the fields our Email model needs. Caller is responsible for dedup.
    """
    results = service.users().messages().list(
        userId="me", maxResults=max_results, labelIds=["INBOX"]
    ).execute()
    message_stubs = results.get("messages", [])

    parsed_messages = []
    for stub in message_stubs:
        msg = service.users().messages().get(
            userId="me", id=stub["id"], format="full"
        ).execute()
        parsed_messages.append(_parse_message(msg))
    return parsed_messages


def _parse_message(msg):
    headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}

    body_text, body_html = _extract_bodies(msg["payload"])

    received_at = None
    if "date" in headers:
        try:
            received_at = parsedate_to_datetime(headers["date"])
        except (TypeError, ValueError):
            received_at = None

    return {
        "message_id": msg["id"],
        "sender": headers.get("from", ""),
        "recipient": headers.get("to", ""),
        "subject": headers.get("subject", ""),
        "body_text": body_text,
        "body_html": body_html,
        "received_at": received_at,
        "source": "gmail",
    }


def _extract_bodies(payload):
    body_text, body_html = "", ""

    def walk(part):
        nonlocal body_text, body_html
        mime_type = part.get("mimeType", "")
        data = part.get("body", {}).get("data")

        if data:
            decoded = base64.urlsafe_b64decode(data.encode("UTF-8")).decode("utf-8", errors="replace")
            if mime_type == "text/plain":
                body_text += decoded
            elif mime_type == "text/html":
                body_html += decoded

        for sub_part in part.get("parts", []):
            walk(sub_part)

    walk(payload)
    return body_text, body_html