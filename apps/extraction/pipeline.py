from django.utils import timezone
from django.utils.html import strip_tags

from apps.records.models import Record

from .attachment_parser import extract_pdf_text, parse_attachment
from .free_text_extractor import extract_free_text_fields
from .html_parser import has_html_table, parse_html_table, parse_key_value_text
from .models import Extraction
from .validation import validate_extraction


def _split_fields(template):
    """(structured_fields, forced_ai_fields) in display order.

    ``structured_fields`` (``is_free_text=False``) go through the deterministic
    ladder first — a table (HTML or a selected spreadsheet attachment), then
    plain-text "Label: value" lines — and only whatever that doesn't resolve
    falls through to AI.
    ``forced_ai_fields`` (``is_free_text=True``) are values the template author
    has flagged as genuinely not derivable from structured parsing (e.g. a name
    mentioned only in a sentence) — they always go straight to AI.
    """
    fields = list(template.fields.all().order_by("display_order", "id"))
    structured_fields = [f for f in fields if not f.is_free_text]
    forced_ai_fields = [f for f in fields if f.is_free_text]
    return structured_fields, forced_ai_fields


def _first_row(parsed):
    """Table parsers return a dict (one row) or list[dict] (batched rows).
    Returns (first_row_dict, all_rows_or_None) for stashing on raw_output."""
    if isinstance(parsed, list):
        return (parsed[0] if parsed else {}), parsed
    return parsed, None


def run_extraction(email, template, attachment=None):
    """
    Full extraction pipeline for one email against one template — a resolution
    ladder, cheapest/most-reliable method first, so AI is only ever asked for
    whatever nothing deterministic could resolve (SRS §10.1, §16 — cost/speed):

    1. Deterministic structured parse: a user-selected spreadsheet attachment
       (SRS §10.1 Phase-2 attachment support) takes priority when given;
       otherwise the email's own HTML table, if it has one.
    2. Deterministic "Label: value" plain-text line parse, for whatever step 1
       didn't find (covers plain-text emails with no table at all — SRS §10.2 —
       and, if a PDF attachment was selected, its extracted text layer).
    3. One batched AI call for whatever steps 1-2 didn't find, plus any field
       explicitly flagged ``is_free_text`` (never attempted deterministically).
    4. Merge — earlier, more-trustworthy steps are never overwritten by later
       ones — validate (Pydantic + confidence stats), create Extraction + DRAFT
       Record.

    ``attachment``: an ``apps.emails.models.Attachment`` the caller explicitly
    picked as this run's data source (e.g. one of several files on the email —
    only THIS file is ever read; the others are never touched). ``None`` (the
    default) extracts from the email body exactly as before attachments existed.

    Returns the Record (or ``None`` if nothing could be extracted at all).
    """
    extraction = Extraction.objects.create(
        email=email, template=template, status=Extraction.Status.PROCESSING
    )

    structured_fields, forced_ai_fields = _split_fields(template)
    structured_names = [f.name for f in structured_fields]
    body_text = email.body_text or strip_tags(email.body_html or "")

    # --- Step 1: deterministic structured source ----------------------------- #
    structured_values: dict = {}
    attachment_note = None
    text_for_ai = body_text

    if attachment is not None and attachment.kind == "spreadsheet":
        parsed, attachment_note = parse_attachment(attachment, structured_names)
        structured_values, table_rows = _first_row(parsed)
        if table_rows is not None:
            extraction.raw_output = {"_table_rows": table_rows}
    elif attachment is not None and attachment.kind == "pdf":
        with attachment.file.open("rb") as fh:
            pdf_text = extract_pdf_text(fh)
        if pdf_text.strip():
            text_for_ai = f"{pdf_text}\n\n{body_text}".strip()
        else:
            attachment_note = (
                f"{attachment.filename} has no extractable text (likely a scanned image)."
            )
    elif attachment is not None:
        attachment_note = (
            f"Attachment type for {attachment.filename!r} isn't supported for automatic "
            "extraction yet (needs OCR); used the email body instead."
        )

    if attachment is None and structured_names and has_html_table(email.body_html):
        parsed = parse_html_table(email.body_html, structured_names)
        structured_values, table_rows = _first_row(parsed)
        if table_rows is not None:
            extraction.raw_output = {"_table_rows": table_rows}

    # --- Step 2: deterministic "Label: value" text-line parse ---------------- #
    still_needed = [n for n in structured_names if n not in structured_values]
    textline_values = parse_key_value_text(text_for_ai, still_needed) if still_needed else {}

    # --- Step 3: one batched AI call for whatever's still missing ----------- #
    resolved_names = set(structured_values) | set(textline_values)
    ai_target_fields = [
        f for f in structured_fields if f.name not in resolved_names
    ] + forced_ai_fields

    ai_values: dict = {}
    ai_error = None
    if ai_target_fields:
        ai_values, ai_error = extract_free_text_fields(text_for_ai, ai_target_fields)

    # Fail only if every step came up empty.
    if not structured_values and not textline_values and not ai_values:
        extraction.status = Extraction.Status.FAILED
        extraction.error_message = ai_error or attachment_note or "No data extracted"
        extraction.processed_at = timezone.now()
        extraction.save()
        return None

    # --- Step 4: merge — structured > text-line > AI on any overlap --------- #
    merged = {**ai_values, **textline_values, **structured_values}
    validated_dict, errors, stats = validate_extraction(template, merged)

    extraction.raw_output = {**extraction.raw_output, **merged}
    extraction.status = Extraction.Status.SUCCESS
    extraction.confidence = (
        f"{stats['required_found']}/{stats['required_total']} required fields"
    )
    notes = [n for n in (
        "; ".join(errors) if errors else None,
        f"AI: {ai_error}" if ai_error else None,
        attachment_note,
    ) if n]
    extraction.error_message = " | ".join(notes)
    extraction.processed_at = timezone.now()
    extraction.save()

    record = Record.objects.create(
        user=email.user,
        email=email,
        template=template,
        extraction=extraction,
        data=validated_dict,
        status=Record.Status.DRAFT,
    )

    email.is_processed = True
    email.save(update_fields=["is_processed"])

    return record
