"""Phase 4 Stage B: full-pipeline evaluation.

Runs every eval case in ``eval_emails.json`` through the ACTUAL production code
paths:
    - apps.extraction.html_parser.parse_html_table   (deterministic table parse)
    - apps.extraction.free_text_extractor.extract_free_text_fields  (focused AI)

Reports three accuracy numbers separately:
    - table-field accuracy   (deterministic; expected ~100%)
    - free-text-field accuracy (this is what we are actually testing the LLM on)
    - overall accuracy
plus the average wall-clock extraction time per email.

Run:
    uv run python spike/run_full_pipeline_eval.py
    uv run python spike/run_full_pipeline_eval.py --limit 3      # quick smoke run
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import django

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.utils.html import strip_tags  # noqa: E402

from apps.extraction.free_text_extractor import extract_free_text_fields  # noqa: E402
from apps.extraction.html_parser import has_html_table, parse_html_table  # noqa: E402
from apps.template.models import Template  # noqa: E402

EVAL_FILE = Path(__file__).parent / "eval_emails.json"


def norm(value) -> str:
    return " ".join(str(value).strip().lower().split())


def compare(expected: dict, actual: dict):
    """Return (correct, total, mismatch_lines) for one field dict."""
    correct, mismatches = 0, []
    for key, exp in expected.items():
        got = actual.get(key)
        if got is not None and norm(got) == norm(exp):
            correct += 1
        else:
            mismatches.append(f"{key}: expected={exp!r} got={got!r}")
    return correct, len(expected), mismatches


def load_free_text_fields(template_name):
    try:
        template = Template.objects.filter(name=template_name).order_by("id").first()
    except Exception:
        template = None
    if template is None:
        sys.exit(
            f"Template {template_name!r} not found. Run:\n"
            f"    uv run python manage.py seed_delivery_instruction_template"
        )
    return list(template.fields.filter(is_free_text=True).order_by("display_order"))


def run(limit=None):
    spec = json.loads(EVAL_FILE.read_text())
    cases = spec["cases"][: limit or None]
    table_fields = spec["table_fields"]
    free_text_field_objs = load_free_text_fields(spec["template"])

    print(f"Eval cases: {len(cases)}  |  template: {spec['template']}")
    print(f"Free-text fields under test: {[f.name for f in free_text_field_objs]}\n")

    tot_tbl_correct = tot_tbl = 0
    tot_ft_correct = tot_ft = 0
    times = []

    for case in cases:
        t0 = time.perf_counter()

        # ---- deterministic table parse -------------------------------------- #
        tbl_actual, tbl_rows = {}, None
        if case.get("has_table") and has_html_table(case["body_html"]):
            parsed = parse_html_table(
                case["body_html"], table_fields, case.get("column_field_map")
            )
            if isinstance(parsed, list):
                tbl_rows = parsed
                tbl_actual = parsed[0] if parsed else {}
            else:
                tbl_actual = parsed

        # ---- focused AI free-text extraction ------------------------------- #
        body = case.get("body_text") or strip_tags(case["body_html"])
        ft_actual, ft_error = extract_free_text_fields(body, free_text_field_objs)

        elapsed = time.perf_counter() - t0
        times.append(elapsed)

        # ---- scoring ------------------------------------------------------- #
        tc, tn, t_miss = compare(case.get("expected_table", {}), tbl_actual)
        fc, fn, f_miss = compare(case.get("expected_free_text", {}), ft_actual)

        # multi-row: also score every expected row against the parsed rows
        row_note = ""
        if case.get("expected_table_rows") and tbl_rows is not None:
            exp_rows = case["expected_table_rows"]
            rc = rn = 0
            padded = tbl_rows + [{}] * len(exp_rows)
            for exp_row, got_row in zip(exp_rows, padded, strict=False):
                c, n, _ = compare(exp_row, got_row or {})
                rc += c
                rn += n
            row_note = f"  [all rows: {rc}/{rn}, parsed {len(tbl_rows)} rows]"

        tot_tbl_correct += tc
        tot_tbl += tn
        tot_ft_correct += fc
        tot_ft += fn

        flag = "OK " if (tc == tn and fc == fn) else "  ! "
        print(
            f"{flag}{case['id']:<34} table {tc}/{tn:<2}  free-text {fc}/{fn}"
            f"  {elapsed:5.1f}s{row_note}"
        )
        for m in t_miss:
            print(f"      table    - {m}")
        for m in f_miss:
            print(f"      freetext - {m}")
        if ft_error:
            print(f"      freetext ! {ft_error}")

    tbl_acc = 100 * tot_tbl_correct / tot_tbl if tot_tbl else float("nan")
    ft_acc = 100 * tot_ft_correct / tot_ft if tot_ft else float("nan")
    overall_correct = tot_tbl_correct + tot_ft_correct
    overall_total = tot_tbl + tot_ft
    overall_acc = 100 * overall_correct / overall_total if overall_total else float("nan")

    print("\n" + "=" * 64)
    print(f"TABLE-FIELD ACCURACY     : {tot_tbl_correct}/{tot_tbl}  ({tbl_acc:.1f}%)")
    print(f"FREE-TEXT-FIELD ACCURACY : {tot_ft_correct}/{tot_ft}  ({ft_acc:.1f}%)")
    print(f"OVERALL ACCURACY         : {overall_correct}/{overall_total}  ({overall_acc:.1f}%)")
    print(f"AVG EXTRACTION TIME/EMAIL: {sum(times) / len(times):.1f}s  "
          f"(min {min(times):.1f}s, max {max(times):.1f}s)")
    print("=" * 64)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="only run the first N cases")
    run(**vars(ap.parse_args()))
