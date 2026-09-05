# Phase 4 (AI Extraction) — Manual Testing Guide

This walks you through verifying the extraction pipeline end to end on your own
machine. Everything here is scoped to `apps/extraction`, the new
**Delivery Instruction** template seed, and the `spike/` eval scripts.

## 0. Prerequisites (one-time)

| Requirement | Check |
|---|---|
| Ollama running with the model | `ollama list` shows `Qwen2.5:7B` |
| Postgres reachable | `uv run python manage.py showmigrations` runs without error |
| A superuser exists | `uv run python manage.py createsuperuser` if not |
| `.env` has `AI_PROVIDER=ollama` and `OLLAMA_MODEL=Qwen2.5:7B` | already set |

> The pipeline calls the local LLM only for the 3 free-text fields. On CPU a call
> takes ~15–25s (the very first call after Ollama starts is ~45–50s while the
> model loads).

## 1. Apply the new migration

```bash
uv run python manage.py migrate template
```

Expected: `Applying template.0002_templatefield_is_free_text... OK`
(adds the boolean `TemplateField.is_free_text`, default `False`).

## 2. Seed the Delivery Instruction template

```bash
uv run python manage.py seed_delivery_instruction_template --user <your-username>
# or omit --user to attach it to the first superuser
```

Expected:

```
Created template 'Delivery Instruction' for user '<you>' — 19 fields (16 table, 3 free-text).
```

Re-running is safe — it wipes the fields and bumps the template version.

Verify the field split:

```bash
uv run python manage.py shell -c "
from apps.template.models import Template
t = Template.objects.get(name='Delivery Instruction')
for f in t.fields.all():
    print(f'{f.display_order:2d} {f.name:26s} {f.data_type:8s} req={f.required!s:5s} free_text={f.is_free_text}')
"
```

The last three (`buyer_name`, `delivery_date`, `delivery_warehouse`) must show
`free_text=True`; the other 16 `False`.

## 3. Unit tests (no LLM, no network)

```bash
uv run pytest apps/extraction -q
```

Expected: `13 passed`.

- `test_html_parser.py` — key-value vs columnar auto-detection, `io.StringIO`
  wrapping, fuzzy header matching, single-dict vs list return, the
  `assorted_qty` / `unassorted_qty` regression.
- `test_pipeline.py` — table + free-text merge, **table values never overwritten
  by AI**, no-table path, multi-row path, total-failure path. The AI provider is
  stubbed here.

> If pytest fails at `permission denied to create database`, grant the app role
> create rights once:
> `sudo -u postgres psql -p <port> -c "ALTER ROLE <db_user> CREATEDB;"`

## 4. Full pipeline eval (uses the LLM — ~5 min for 13 cases)

```bash
uv run python spike/run_full_pipeline_eval.py            # all 13 cases
uv run python spike/run_full_pipeline_eval.py --limit 3  # quick smoke run
```

This runs every case in `spike/eval_emails.json` through the **real**
`html_parser.parse_html_table` and `free_text_extractor.extract_free_text_fields`
code and prints three separate accuracy numbers plus average time per email.

Reference numbers from the last run on this machine:

```
TABLE-FIELD ACCURACY     : 86/86   (100.0%)
FREE-TEXT-FIELD ACCURACY : 38/39   (97.4%)
OVERALL ACCURACY         : 124/125 (99.2%)
AVG EXTRACTION TIME/EMAIL: 20.8s
```

Table accuracy is deterministic and should be 100% every run. Free-text accuracy
depends on the model and may wobble ±1 field between runs (temperature is 0, but
Qwen is not perfectly deterministic on CPU). The single known miss is
`di_13_no_table_buyer_only_in_greeting` — buyer named only in "Dear ABA FASHIONS
LTD team,".

## 5. End-to-end through the Django pipeline (the real thing)

### 5a. Create an Email row from the real .eml content

```bash
uv run python manage.py shell <<'EOF'
import json
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.emails.models import Email

case = json.load(open("spike/eval_emails.json"))["cases"][0]   # di_01 = real ABA FASHIONS
user = get_user_model().objects.filter(is_superuser=True).order_by("id").first()

email, created = Email.objects.update_or_create(
    message_id="<real-aba-fashions-QID-2793757@vendor.example>",
    defaults=dict(
        user=user,
        sender="vendor.coordination@abafashions-supplier.example",
        subject="Delivery Instruction / ABA FASHIONS LTD #QID:2793757",
        body_html=case["body_html"],
        received_at=timezone.now(),
        source="manual-eml-import",
        is_processed=False,
    ),
)
print("email id:", email.id, "created:", created)
EOF
```

> If you have an actual `.eml` file, parse it with `email.message_from_binary_file`
> and drop the HTML part into `body_html` instead of using the eval fixture.

### 5b. Run extraction

There's no CLI extraction command — extraction is always triggered per-email
from the Inbox UI (`/inbox/` → **Extract →**), so template (and attachment)
choice is always an explicit human decision, never guessed. Easiest path:
log in, open Inbox, click **Extract →** on the email from step 5a, confirm the
template in the dialog.

To drive it from the shell instead (e.g. for scripting), call the pipeline
function directly — it's the same code the UI calls:

```bash
uv run python manage.py shell <<'EOF'
from apps.emails.models import Email
from apps.template.models import Template
from apps.extraction.pipeline import run_extraction

email = Email.objects.get(message_id="<real-aba-fashions-QID-2793757@vendor.example>")
template = Template.objects.get(name="Delivery Instruction")
record = run_extraction(email, template)
print("Draft record #%d created (%s)" % (record.id, record.data) if record else "Extraction failed")
EOF
```

### 5c. Inspect the draft Record

```bash
uv run python manage.py shell <<'EOF'
import json
from apps.records.models import Record
r = Record.objects.filter(template__name="Delivery Instruction").latest("id")
print("Record #%d status=%s (expect DRAFT)" % (r.id, r.status))
print("Extraction status=%s confidence=%s" % (r.extraction.status, r.extraction.confidence))
print(json.dumps(r.data, indent=2))
EOF
```

**Pass criteria:**

- `Record.status == "DRAFT"`
- `Record.data` (JSONB) contains **all 16 table-derived values**
  (`order_no`, `cps_id`, `special_code`, `style_name`, `assorted_qty`,
  `unassorted_qty`, `total_cartons`, `final_destination`,
  `delivery_place_of_vendor`, `target_shipment`, `shipment_route`, `lc_ref_no`,
  `lc_ref_bank`, `delivery_location`, `vehicle_type`, `gtip`)
- **and all 3 free-text values** (`buyer_name` = "ABA FASHIONS LTD",
  `delivery_date` = "2026-08-25", `delivery_warehouse` = "Chittagong Warehouse")
- `Extraction.confidence` == "7/7 required fields"

Reference output for this email:

```json
{
  "order_no": "ORD-2793757", "cps_id": "CPS-88213", "special_code": "SC-09",
  "style_name": "Mens Crew Neck Tee", "assorted_qty": 12000, "unassorted_qty": 1500,
  "total_cartons": 420, "final_destination": "Hamburg",
  "delivery_place_of_vendor": "Chittagong", "target_shipment": "W35-2026",
  "shipment_route": "CTG-HAM via Colombo", "lc_ref_no": "LC-4471902",
  "lc_ref_bank": "Standard Chartered", "delivery_location": "Chittagong Port",
  "vehicle_type": "Covered Van", "gtip": "6109.10.00.00",
  "buyer_name": "ABA FASHIONS LTD", "delivery_date": "2026-08-25",
  "delivery_warehouse": "Chittagong Warehouse"
}
```

### 5d. Re-run cleanly

```bash
uv run python manage.py shell -c "
from apps.emails.models import Email
from apps.records.models import Record
from apps.extraction.models import Extraction
Record.objects.filter(template__name='Delivery Instruction').delete()
Extraction.objects.filter(template__name='Delivery Instruction').delete()
Email.objects.filter(source='manual-eml-import').update(is_processed=False)
print('reset done')
"
```

## 6. Try your own emails

- **Columnar table**: headers just need to resemble the field names
  (case / spaces / hyphens / dots are ignored). Unmatched columns are skipped.
- **Weird headers**: pass an explicit map when calling directly —
  `parse_html_table(html, field_names, column_field_map={"Ctns": "total_cartons"})`.
- **Multi-row table**: the Record keeps row 1; every row is stored on
  `Extraction.raw_output["_table_rows"]`.
- **No table**: only the 3 free-text fields are filled (all-AI path).

## What changed in Phase 4

| File | Change |
|---|---|
| `apps/template/models.py` (+ migration `0002`) | new `TemplateField.is_free_text` boolean |
| `apps/extraction/html_parser.py` | `io.StringIO` wrap on every `pd.read_html`; key-value vs columnar auto-detect; fuzzy header matching + explicit `column_field_map`; native-int values; single-dict / list return |
| `apps/extraction/free_text_extractor.py` | **new** — focused prompt for only the `is_free_text` fields, via `providers.get_provider()` |
| `apps/extraction/pipeline.py` | splits fields by `is_free_text`, merges table (ground truth) + free-text AI, table wins on overlap |
| `apps/extraction/management/commands/seed_delivery_instruction_template.py` | **new** — 19-field Delivery Instruction template |
| `spike/eval_emails.json` | 13 cases (real ABA + 12 invented), table vs free-text expectations split |
| `spike/run_full_pipeline_eval.py` | **new** — runs cases through real pipeline code, reports 3 accuracies + timing |
| `pyproject.toml` | added `lxml` (pandas HTML parser backend — was missing) |

`apps/extraction/prompt_builder.py` (the old whole-schema prompt) is no longer
called by the pipeline; left in place unused.
