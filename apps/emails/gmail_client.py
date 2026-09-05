"""Gmail API message fetching + MIME parsing.

The authenticated ``service`` object is built by ``providers.GmailProvider``
from the OAuth token stored on the user's ``EmailAccount`` — this module only
turns a Gmail message into our normalized dict shape.
"""

import base64
from email.utils import parsedate_to_datetime


def fetch_new_messages(service, max_results=25):
    """
    Fetches recent messages from the inbox. Returns a list of dicts with
    the fields our Email model needs, including a resolved ``attachments``
    list (filename / content_type / size / content bytes). Caller is
    responsible for dedup.
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
        parsed_messages.append(_parse_message(service, msg))
    return parsed_messages


def _parse_message(service, msg):
    headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}

    body_text, body_html, attachment_parts = _extract_bodies_and_attachments(msg["payload"])
    attachments = _resolve_attachments(service, msg["id"], attachment_parts)

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
        "attachments": attachments,
    }


def _extract_bodies_and_attachments(payload):
    body_text, body_html = "", ""
    attachment_parts = []

    def walk(part):
        nonlocal body_text, body_html
        mime_type = part.get("mimeType", "")
        body = part.get("body", {})
        filename = part.get("filename", "")

        if filename:
            # A real attachment (or inline image) — filename is only ever set
            # on parts Gmail considers a file, never on the text/html body parts.
            attachment_parts.append(
                {
                    "filename": filename,
                    "content_type": mime_type,
                    "attachment_id": body.get("attachmentId"),
                    "inline_data": body.get("data"),  # small attachments only
                    "size": body.get("size", 0),
                }
            )
        elif body.get("data"):
            decoded = base64.urlsafe_b64decode(body["data"].encode("UTF-8")).decode(
                "utf-8", errors="replace"
            )
            if mime_type == "text/plain":
                body_text += decoded
            elif mime_type == "text/html":
                body_html += decoded

        for sub_part in part.get("parts", []):
            walk(sub_part)

    walk(payload)
    return body_text, body_html, attachment_parts


def _resolve_attachments(service, message_id, attachment_parts):
    """Download each attachment's bytes (small ones already arrived inline;
    larger ones need a separate Gmail API call keyed by attachmentId)."""
    attachments = []
    for part in attachment_parts:
        data = part["inline_data"]
        if not data and part["attachment_id"]:
            fetched = (
                service.users()
                .messages()
                .attachments()
                .get(userId="me", messageId=message_id, id=part["attachment_id"])
                .execute()
            )
            data = fetched.get("data")
        if not data:
            continue

        content = base64.urlsafe_b64decode(data.encode("UTF-8"))
        attachments.append(
            {
                "filename": part["filename"],
                "content_type": part["content_type"],
                "size": part["size"] or len(content),
                "content": content,
            }
        )
    return attachments
