"""Flatten JSONB records into tabular rows for CSV / Excel export (SRS §12.7)."""

from apps.records.models import Record


def get_records(user, template_id=None, status=None, created_after=None, created_before=None):
    qs = (
        Record.objects.filter(user=user)
        .select_related("email", "template", "approved_by")
        .prefetch_related("template__fields")
        .order_by("-created_at")
    )
    if template_id:
        qs = qs.filter(template_id=template_id)
    if status:
        qs = qs.filter(status=status.upper())
    if created_after:
        qs = qs.filter(created_at__date__gte=created_after)
    if created_before:
        qs = qs.filter(created_at__date__lte=created_before)
    return qs


def build_table(records):
    """Return (headers, rows). Field columns come from the templates involved;
    when several templates are mixed, their field sets are unioned."""
    records = list(records)

    field_columns: list[str] = []
    field_labels: dict[str, str] = {}
    seen = set()
    for rec in records:
        for f in rec.template.fields.all().order_by("display_order", "id"):
            if f.name not in seen:
                seen.add(f.name)
                field_columns.append(f.name)
                field_labels[f.name] = f.label or f.name
    # any stray keys present in data but not in the schema
    for rec in records:
        for key in rec.data:
            if key not in seen:
                seen.add(key)
                field_columns.append(key)
                field_labels[key] = key

    meta_headers = ["record_id", "template", "status", "email_subject", "email_sender",
                    "approved_by", "approved_at", "created_at"]
    headers = meta_headers + [field_labels[c] for c in field_columns]

    rows = []
    for rec in records:
        meta = [
            rec.id,
            rec.template.name,
            rec.get_status_display(),
            rec.email.subject,
            rec.email.sender,
            rec.approved_by.username if rec.approved_by_id else "",
            rec.approved_at.isoformat() if rec.approved_at else "",
            rec.created_at.isoformat(),
        ]
        rows.append(meta + [_cell(rec.data.get(c)) for c in field_columns])
    return headers, rows


def _cell(value):
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        import json

        return json.dumps(value, ensure_ascii=False)
    return value
