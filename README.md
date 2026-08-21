# Mail2Record

Mail2Record turns incoming emails into structured records: emails are ingested,
their content is extracted (HTML parsing, LLM-assisted extraction via Ollama),
and the results are stored, reviewed, and exported (e.g. to Excel).

**Status:** Phase 0 — project skeleton. Django + DRF backend with a
server-rendered template frontend (jQuery), backed by PostgreSQL.

## Tech stack

| Layer      | Technology                                        |
|------------|---------------------------------------------------|
| Language   | Python 3.13                                       |
| Framework  | Django 6.1 + Django REST Framework                |
| Database   | PostgreSQL 17 (psycopg 3)                         |
| Frontend   | Django Templates + jQuery 3.7 (no SPA framework)  |
| Env/secrets| python-decouple (`.env` file)                     |
| Tooling    | uv (venv + deps), black, ruff, pytest-django      |

## Prerequisites

- Ubuntu with Python 3.13
- [uv](https://docs.astral.sh/uv/) installed
- PostgreSQL running locally

## Getting started

### 1. Install dependencies

```bash
uv sync
```

This creates `.venv` and installs everything from `uv.lock`.

### 2. Configure the database

Create a role and database (adjust the password):

```bash
sudo -u postgres psql -c "CREATE ROLE mail2record_app WITH LOGIN PASSWORD '<password>';"
sudo -u postgres psql -c "CREATE DATABASE mail2record_dev OWNER mail2record_app;"
```

> **Note:** on this machine multiple PostgreSQL clusters are installed;
> cluster 17 listens on port **5434** (not the default 5432).

### 3. Set up environment variables

```bash
cp .env.example .env
```

Then edit `.env` and set real values:

```
SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_urlsafe(64))">
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DB_NAME=mail2record_dev
DB_USER=mail2record_app
DB_PASSWORD=<password>
DB_HOST=127.0.0.1
DB_PORT=5434
CORS_ALLOWED_ORIGINS=
```

Never commit `.env` — it is gitignored.

### 4. Run migrations

```bash
uv run python manage.py migrate
```

### 5. Start the dev server

```bash
uv run python manage.py runserver
```

Visit <http://127.0.0.1:8000/>:

- The dashboard page loads with the nav bar.
- The "API health" section shows **ok** — this is a live jQuery AJAX call to
  `GET /api/health/`, proving templates + jQuery + DRF are wired end-to-end.

If port 8000 is taken, use another: `uv run python manage.py runserver 8010`.

## Project layout

```
mail2record/
├── config/            # Project package: settings, root urls, API routes/views
├── apps/              # All Django apps live here (referenced as apps.<name>)
│   ├── accounts/      # User accounts & auth (Phase 1)
│   ├── templates_app/ # Email/record template definitions (Phase 1)
│   ├── emails/        # Email ingestion (Phase 1)
│   ├── extraction/    # Content extraction incl. Ollama LLM calls (Phase 1)
│   ├── records/       # Structured record storage (Phase 1)
│   ├── exports/       # Excel/CSV export (Phase 1)
│   └── dashboard/     # Dashboard pages (has a placeholder view now)
├── templates/         # Project-level templates (base.html)
└── static/            # CSS, JS, vendored jQuery
```

## API

| Endpoint          | Method | Auth      | Description                  |
|-------------------|--------|-----------|------------------------------|
| `/api/health/`    | GET    | Public    | Liveness probe `{"status":"ok"}` |

## Development

All commands run through `uv run` so they use the project venv.

```bash
# Format code
uv run black .

# Lint
uv run ruff check .

# Run tests (once tests exist)
uv run pytest
```

### Branch convention

- `main` — always deployable
- `feature/<short-name>` — feature branches merged into `main`

## Out of scope (per SRS)

Celery, Redis, Docker, and JS frameworks (React/Vue/etc.) are explicitly out of
scope for Phase 0/MVP. DRF and jQuery are the only additions to the core stack.
