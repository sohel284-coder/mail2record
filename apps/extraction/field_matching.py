"""Fuzzy label/column matching shared by every deterministic parser
(HTML tables, plain-text "Label: value" lines, spreadsheet attachments).

Kept in one place so a template's field list works the same way regardless of
which structured source it's being matched against.
"""

import pandas as pd


def normalize(text) -> str:
    """Case / whitespace / punctuation-insensitive key for fuzzy matching."""
    text = str(text).strip().lower().rstrip(":")
    for ch in ("_", "-", ".", "/", "\\", "\n", "\t", "(", ")", "#"):
        text = text.replace(ch, " ")
    return " ".join(text.split())


def squash(text) -> str:
    """Normalized key with all whitespace removed (last-resort fuzzy match)."""
    return normalize(text).replace(" ", "")


def clean_value(value):
    """Convert numpy scalars to native Python and trim strings; drop NaN/empty."""
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if hasattr(value, "item"):  # numpy int64 / float64 / bool_
        value = value.item()
    if isinstance(value, str):
        value = value.strip()
        if value == "" or value.lower() in {"nan", "none", "-"}:
            return None
    return value


def match_label(label: str, normalized_fields: dict[str, str]) -> str | None:
    """``normalized_fields``: {normalize(field_name): field_name}. Two-way
    substring containment — used for short "label: value" style text where a
    field's name/label is often a near-exact match of the label as written."""
    for norm_label, field_name in normalized_fields.items():
        if norm_label and (norm_label == label or norm_label in label or label in norm_label):
            return field_name
    return None


def match_column(target, normalized_columns, squashed_columns):
    """Find the real column best matching ``target`` (a header or field name).

    Matching is tried strongest-first: exact normalized, exact whitespace-
    squashed, then containment (target is a substring of a column header). The
    reverse containment (header inside target) is deliberately NOT used — it
    would let e.g. ``unassorted_qty`` swallow an ``Assorted Qty`` column.
    """
    nt = normalize(target)
    if nt in normalized_columns:
        return normalized_columns[nt]
    st = squash(target)
    if st and st in squashed_columns:
        return squashed_columns[st]
    for norm_col, actual in normalized_columns.items():
        if nt and nt in norm_col:
            return actual
    return None


def resolve_column_map(df_columns, field_names, column_field_map=None):
    """Return {actual_df_column: template_field_name}.

    If an explicit ``column_field_map`` ({source_header: field_name}) is given
    we fuzzy-match its keys against the real columns. Otherwise we fuzzy-match
    the ``field_names`` themselves against the columns directly.
    """
    normalized_columns = {normalize(c): c for c in df_columns}
    squashed_columns = {squash(c): c for c in df_columns}
    resolved: dict = {}

    if column_field_map:
        for source_header, field_name in column_field_map.items():
            col = match_column(source_header, normalized_columns, squashed_columns)
            if col is not None:
                resolved[col] = field_name
        return resolved

    for field_name in field_names:
        col = match_column(field_name, normalized_columns, squashed_columns)
        if col is not None:
            resolved[col] = field_name
    return resolved


def dataframe_to_records(df, field_names, column_field_map=None) -> list[dict]:
    """Shared columnar-dataframe -> [{field_name: value}] conversion, used by
    both the HTML columnar-table parser and the spreadsheet-attachment parser."""
    col_map = resolve_column_map(df.columns, field_names, column_field_map)

    records: list[dict] = []
    for _, row in df.iterrows():
        record: dict = {}
        for actual_col, field_name in col_map.items():
            value = clean_value(row[actual_col])
            if value is not None:
                record[field_name] = value
        if record:
            records.append(record)
    return records
