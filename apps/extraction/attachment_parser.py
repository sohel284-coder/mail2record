"""Deterministic parsing for a user-selected email attachment.

Attachments are never parsed automatically / blindly — a run only ever reads
the ONE attachment a person explicitly picked in the extract-confirm dialog
(see ``apps.emails.api_views.EmailViewSet.extract``). That keeps behaviour
predictable and keeps every other file's bytes away from the LLM entirely.

Supported today:
- Spreadsheets (.csv / .xlsx / .xls) — deterministic, via pandas, reusing the
  exact same fuzzy column matching as the HTML table parser.
- PDFs with a text layer — best-effort text extraction (via the system
  ``pdftotext`` tool, no extra Python dependency) fed through the same
  "Label: value" line parser used for plain-text email bodies, then whatever's
  still missing goes to the AI step same as always.

Not supported yet (SRS §10.1 explicitly defers this): scanned/image-only PDFs
and image attachments (.png/.jpg/...) need OCR, which isn't wired in. These
report a clear "extraction_error" instead of silently returning nothing.
"""

import io
import subprocess

import pandas as pd

from .field_matching import dataframe_to_records
from .html_parser import parse_key_value_text


def parse_spreadsheet_attachment(
    file_obj, filename: str, field_names: list[str], column_field_map: dict | None = None
):
    """``file_obj``: any file-like object opened in binary mode (Django's
    ``FieldFile`` works directly). Returns a dict (single row) or list[dict]
    (multiple rows), same convention as ``html_parser.parse_html_table``.
    """
    name = filename.lower()
    if name.endswith(".csv"):
        df = pd.read_csv(file_obj)
    elif name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(file_obj)
    else:
        raise ValueError(f"Unsupported spreadsheet type: {filename}")

    records = dataframe_to_records(df, field_names, column_field_map)
    if not records:
        return {}
    if len(records) == 1:
        return records[0]
    return records


def extract_pdf_text(file_obj) -> str:
    """Best-effort text-layer extraction via the system ``pdftotext`` binary.
    Returns "" if the tool is missing or the PDF has no extractable text
    (e.g. a scanned image) — callers should treat "" as "nothing found",
    not an error, and fall back to whatever the email body itself offers.
    """
    try:
        proc = subprocess.run(
            ["pdftotext", "-layout", "-", "-"],
            input=file_obj.read(),
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""
    if proc.returncode != 0:
        return ""
    return proc.stdout.decode("utf-8", errors="replace")


def parse_attachment(attachment, field_names: list[str], column_field_map: dict | None = None):
    """Route to the right parser by ``attachment.kind``.

    Returns ``(values, error)``:
    - spreadsheet: ``values`` is a dict/list[dict] per ``parse_spreadsheet_attachment``.
    - pdf: ``values`` is a dict from running the deterministic text-line parser
      over the extracted text (may be empty if the PDF has no text layer —
      that's reported via ``error``, not raised).
    - image / other: ``values`` is always ``{}`` with an explanatory ``error``.
    """
    kind = attachment.kind

    if kind == "spreadsheet":
        try:
            with attachment.file.open("rb") as fh:
                values = parse_spreadsheet_attachment(
                    io.BytesIO(fh.read()), attachment.filename, field_names, column_field_map
                )
            return values, None
        except Exception as exc:  # pandas raises many distinct error types
            return {}, f"Could not read {attachment.filename}: {exc}"

    if kind == "pdf":
        with attachment.file.open("rb") as fh:
            text = extract_pdf_text(fh)
        if not text.strip():
            return {}, f"{attachment.filename} has no extractable text (likely a scanned image)."
        return parse_key_value_text(text, field_names), None

    return {}, (
        f"Attachment type for {attachment.filename!r} isn't supported for automatic "
        "extraction yet (needs OCR)."
    )
