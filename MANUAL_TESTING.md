# Mail2Record — MVP Manual Test Guide

End-to-end walkthrough of the whole SRS flow:

> Email → Collector → stored → template selected → AI extraction → validation →
> DRAFT → review / edit → approve → PostgreSQL → web table → Excel / CSV

Everything runs locally: Django + PostgreSQL + Ollama, no cloud.

---

## 0. One-time setup

```bash
# 1. database + migrations
uv run python manage.py migrate

# 2. a user to log in as
uv run python manage.py createsuperuser

# 3. Ollama running with the model (separate terminal / service)
ollama serve &
ollama pull qwen2.5:7b        # matches OLLAMA_MODEL in .env (Qwen2.5:7B)

# 4. seed the sample template
uv run python manage.py seed_delivery_instruction_template --user <username>

# 5. run the app
uv run python manage.py runserver
```

Open http://127.0.0.1:8000/ and sign in.

`.env` keys that matter: `DB_*`, `AI_PROVIDER=ollama`, `OLLAMA_MODEL=Qwen2.5:7B`.

---

## 1. Login  (SRS §12.1)

- Go to `/` → redirected to `/login/`.
- Wrong password → "Invalid username or password."
- Correct → lands on the dashboard. The left rail now shows Overview / Inbox /
  Templates / Review queue / Records / Settings.

## 2. Dashboard  (SRS §12.2)

`/` — check the four tiles (Emails processed, Drafts to review, Approved records,
Active templates) show real counts, and "Recent drafts" lists up to 3 drafts each
linking into review. "See all drafts →" goes to the review queue.

## 3. Templates  (SRS §12.4 / §12.5)

- `/templates/` lists templates with field count + version + active flag.
- **Delivery Instruction** should be there with 19 fields.
- `/templates/new/`:
  - Upload a CSV/XLSX whose first row is column headers → **Detect columns** →
    the field table fills in with guessed types. Adjust names/types/required.
  - Or **+ Add field manually**.
  - Save → returns to the list; edit re-opens the same fields.

## 4. Collect email  (SRS §11)

**Option A — real Gmail:**
```bash
uv run python manage.py fetch_emails --user <username>
```
First run opens a browser for OAuth; the token is cached afterwards. Re-running
skips anything already stored (dedup on `message_id`).

**Option B — no Gmail set up:** create a test email in the Django shell:
```bash
uv run python manage.py shell
```
```python
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.emails.models import Email

u = get_user_model().objects.get(username="<username>")
Email.objects.create(
    user=u, message_id="test-di-001",
    sender="ops@vendor.example",
    subject="Delivery Instruction / ABA FASHIONS LTD #QID:2793757",
    body_html="""
    <p>Please arrange delivery for <b>ABA FASHIONS LTD</b>. The cargo must reach the
    <b>Chittagong Warehouse</b> no later than 25-08-2026 16:00.</p>
    <table>
      <tr><th>Order No</th><th>CPS ID</th><th>Style Name</th><th>Total Cartons</th><th>Final Destination</th></tr>
      <tr><td>ORD-2793757</td><td>CPS-88213</td><td>Mens Crew Neck Tee</td><td>420</td><td>Hamburg</td></tr>
    </table>""",
    received_at=timezone.now(), source="manual", is_processed=False,
)
```
(There are 13 ready-made sample bodies in `spike/eval_emails.json`.)

## 5. Inbox → run extraction  (SRS §12.3 / §4.2 / §10)

`/inbox/`:
- Search by sender/subject/message-id; filter Unprocessed / Processed.
- On an **Unprocessed** row click **Extract →** — this opens a confirm dialog
  naming the template that will be used (your default, or the first active one
  if no default is set — see the Templates page) and lets you pick a different
  one. If the email has attachments, a second picker appears: "Extract from"
  (email body, or one specific attachment — only that one file is ever read).
- Confirming runs the full pipeline locally: deterministic table/attachment
  parse + text-line parse for structured fields, then one focused LLM call for
  whatever's still missing. Takes ~15–75s depending on how much falls to AI.
- On success you're taken straight to the draft review screen.
- Processed rows show **Review →** (jumps to their draft).

There is no CLI/batch extraction command — extraction is always a deliberate,
per-email action from the Inbox, so template (and attachment) choice is always
explicit rather than guessed.

## 6. Draft review — the core screen  (SRS §12.6)

`/review/<id>/` — side by side:

**Left:** the original email (plain text, or the HTML rendered in a sandboxed
iframe). Never modified.

**Right:** every template field as an editable input, in display order, tagged
Required/Optional and "from table" vs "from free text (AI)". A banner at the top
shows the review indicator (e.g. "7/7 required fields") — a practical checklist,
not a fake accuracy % (SRS §10.4).

- Edit any wrong value → "Unsaved changes" appears → **Save edits** (PATCH).
- **Approve →** saves any pending edits, stamps `approved_by` + `approved_at`,
  moves the record to APPROVED, returns to the queue.
- **Reject** → record goes to REJECTED (kept for audit, excluded from exports).
- Re-approving or editing an already-decided record is blocked (409 / 400).

Checks:
- Table-derived values (order_no, cps_id, …) match the email table exactly.
- Free-text values (buyer_name, delivery_date as YYYY-MM-DD, delivery_warehouse)
  are filled from the prose.
- Leaving a required field empty flips the banner to a warning.

## 7. Review queue  (SRS §4.2)

`/review/` — every DRAFT record, newest first, with its confidence indicator.
Empty state tells you to run extraction from the inbox.

## 8. Records + export  (SRS §12.7 / §13)

`/records/`:
- Filter by template, status (defaults to Approved), and created-date range;
  free-text search hits subject/sender/extracted values.
- Each row shows a few key extracted values and links to the record detail
  (`/records/<id>/`) or back into review if still a draft.
- **↓ CSV** and **↓ Excel** download the *currently filtered* set. One row per
  record; columns are `record_id, template, status, email_subject, email_sender,
  approved_by, approved_at, created_at` followed by one column per template
  field (unioned when several templates are mixed). Multi-row table records keep
  line 1 here; every parsed line is on `Extraction.raw_output["_table_rows"]`.

Direct URLs: `/exports/records.csv?status=APPROVED&template=<id>`,
`/exports/records.xlsx?...`

## 9. Settings  (SRS §16)

`/settings/` — read-only status: AI provider + model, Gmail token connected?,
template/record counts, links to records and Django admin, sign out.

## 10. Original data is preserved  (SRS §17)

At every step the `emails` row is untouched — approving/editing only ever writes
the `records.data` JSONB. Confirm in `/admin/` → Emails that `body_html` /
`body_text` are exactly as collected.

---

## Automated tests

```bash
uv run pytest -q          # 19 tests: html parser, extraction pipeline, records API
```

(If pytest can't create its test DB: `sudo -u postgres psql -p 5434 -c "ALTER
ROLE mail2record_app CREATEDB;"` once.)

## Extraction accuracy / model quality

See `spike/PHASE4_MANUAL_TESTING.md` and `spike/run_full_pipeline_eval.py` —
last run: table 100%, free-text 97.4%, overall 99.2%, ~20s/email.
