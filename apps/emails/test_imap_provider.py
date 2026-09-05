"""IMAP message parsing + host guessing (no live IMAP server)."""

from email.message import EmailMessage

from apps.emails.providers import _parse_imap_message, guess_imap_host


def _build_raw(with_attachment=False):
    msg = EmailMessage()
    msg["Message-ID"] = "<abc-123@vendor.test>"
    msg["From"] = "Vendor Ops <ops@vendor.test>"
    msg["To"] = "me@example.com"
    msg["Subject"] = "Booking PO-45892"
    msg["Date"] = "Mon, 01 Sep 2026 09:30:00 +0000"
    msg.set_content("Plain text body\nPO No: PO-45892")
    msg.add_alternative("<p>HTML body</p>", subtype="html")
    if with_attachment:
        msg.add_attachment(
            b"order_no,total\nORD-1,5\n",
            maintype="text", subtype="csv", filename="orders.csv",
        )
    return msg.as_bytes()


def test_parses_headers_bodies_and_source():
    parsed = _parse_imap_message(_build_raw())
    assert parsed["message_id"] == "<abc-123@vendor.test>"
    assert parsed["subject"] == "Booking PO-45892"
    assert parsed["sender"] == "Vendor Ops <ops@vendor.test>"
    assert "PO No: PO-45892" in parsed["body_text"]
    assert "HTML body" in parsed["body_html"]
    assert parsed["source"] == "imap"
    assert parsed["received_at"] is not None
    assert parsed["attachments"] == []


def test_parses_attachment_bytes():
    parsed = _parse_imap_message(_build_raw(with_attachment=True))
    assert len(parsed["attachments"]) == 1
    att = parsed["attachments"][0]
    assert att["filename"] == "orders.csv"
    assert att["content"] == b"order_no,total\nORD-1,5\n"
    assert att["size"] == len(att["content"])


def test_message_without_message_id_gets_a_stable_fallback():
    msg = EmailMessage()
    msg["Subject"] = "No id"
    msg.set_content("hi")
    raw = msg.as_bytes()
    a = _parse_imap_message(raw)
    b = _parse_imap_message(raw)
    assert a["message_id"].startswith("imap-")
    assert a["message_id"] == b["message_id"]


def test_host_guessing():
    assert guess_imap_host("x@gmail.com") == ("imap.gmail.com", 993)
    assert guess_imap_host("x@outlook.com") == ("outlook.office365.com", 993)
    assert guess_imap_host("x@some-random-corp.example") == (None, 993)
