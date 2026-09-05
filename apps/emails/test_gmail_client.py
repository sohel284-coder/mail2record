"""Gmail MIME-walking + attachment resolution — synthetic payloads, no network."""

import base64

from apps.emails.gmail_client import _extract_bodies_and_attachments, _resolve_attachments


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode()


def test_extract_bodies_and_attachments_separates_text_html_and_files():
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {
                "mimeType": "multipart/alternative",
                "parts": [
                    {"mimeType": "text/plain", "body": {"data": _b64("Hello plain")}},
                    {"mimeType": "text/html", "body": {"data": _b64("<p>Hello html</p>")}},
                ],
            },
            {
                "mimeType": "text/csv",
                "filename": "orders.csv",
                "body": {"attachmentId": "ATT123", "size": 42},
            },
            {
                "mimeType": "application/pdf",
                "filename": "packing_list.pdf",
                "body": {"data": _b64("small inline pdf"), "size": 16},
            },
        ],
    }

    body_text, body_html, attachments = _extract_bodies_and_attachments(payload)

    assert body_text == "Hello plain"
    assert body_html == "<p>Hello html</p>"
    assert len(attachments) == 2
    csv_part, pdf_part = attachments
    assert csv_part["filename"] == "orders.csv"
    assert csv_part["attachment_id"] == "ATT123"
    assert csv_part["inline_data"] is None
    assert pdf_part["filename"] == "packing_list.pdf"
    assert pdf_part["inline_data"] is not None


class _FakeAttachmentsResource:
    def __init__(self, data_by_id):
        self.data_by_id = data_by_id
        self.calls = []

    def get(self, userId, messageId, id):  # noqa: A002 - matches googleapiclient's signature
        self.calls.append((messageId, id))
        return _FakeExecutable(self.data_by_id[id])


class _FakeExecutable:
    def __init__(self, data):
        self._data = data

    def execute(self):
        return {"data": self._data}


class _FakeMessagesResource:
    def __init__(self, attachments_resource):
        self._attachments = attachments_resource

    def attachments(self):
        return self._attachments


class _FakeService:
    def __init__(self, data_by_id):
        self._messages = _FakeMessagesResource(_FakeAttachmentsResource(data_by_id))

    def users(self):
        return self

    def messages(self):
        return self._messages


def test_resolve_attachments_downloads_only_parts_without_inline_data():
    service = _FakeService({"ATT123": _b64("order_no,total_cartons\nORD-1,420\n")})
    parts = [
        {
            "filename": "orders.csv", "content_type": "text/csv",
            "attachment_id": "ATT123", "inline_data": None, "size": 0,
        },
        {
            "filename": "note.txt", "content_type": "text/plain",
            "attachment_id": None, "inline_data": _b64("inline body"), "size": 11,
        },
    ]

    resolved = _resolve_attachments(service, "msg-1", parts)

    assert len(resolved) == 2
    assert resolved[0]["filename"] == "orders.csv"
    assert resolved[0]["content"] == b"order_no,total_cartons\nORD-1,420\n"
    assert resolved[1]["filename"] == "note.txt"
    assert resolved[1]["content"] == b"inline body"
    # only the part lacking inline data triggered a network call
    assert service._messages._attachments.calls == [("msg-1", "ATT123")]
