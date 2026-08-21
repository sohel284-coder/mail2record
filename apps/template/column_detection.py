"""Deterministic column detection for uploaded CSV/Excel template sources."""

import pandas as pd

MAX_PREVIEW_ROWS = 20


def detect_columns(uploaded_file):
    """
    Read an uploaded CSV/XLSX file and return a list of detected columns
    with a guessed data type, based on pandas dtype inference.
    """
    name = uploaded_file.name.lower()

    if name.endswith(".csv"):
        df = pd.read_csv(uploaded_file, nrows=MAX_PREVIEW_ROWS)
    elif name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(uploaded_file, nrows=MAX_PREVIEW_ROWS)
    else:
        raise ValueError("Unsupported file type. Upload a .csv, .xlsx, or .xls file.")

    if df.empty and len(df.columns) == 0:
        raise ValueError("The file has no columns to detect.")

    columns = []
    for order, col in enumerate(df.columns, start=1):
        columns.append(
            {
                "name": _to_machine_name(col),
                "label": str(col).strip(),
                "data_type": _guess_type(df[col]),
                "required": False,
                "description": "",
                "ai_instruction": "",
                "display_order": order,
            }
        )
    return columns


def _to_machine_name(col):
    return str(col).strip().lower().replace(" ", "_").replace("-", "_").replace("/", "_")


def _guess_type(series):
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_integer_dtype(series):
        return "integer"
    if pd.api.types.is_float_dtype(series):
        return "number"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "date"

    # pandas often reads dates/numbers as object/string; try light coercion
    non_null = series.dropna()
    if non_null.empty:
        return "string"

    try:
        pd.to_datetime(non_null, errors="raise")
        return "date"
    except (ValueError, TypeError):
        pass

    try:
        pd.to_numeric(non_null, errors="raise")
        return "number"
    except (ValueError, TypeError):
        pass

    return "string"
