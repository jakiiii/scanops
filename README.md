# ScanOps

ScanOps is an internal authorized-use network/security operations platform built around controlled Nmap-style workflows.  
It is designed for approved internal environments, approved internal assets, and explicitly permitted targets.

## Stack

- Django (MVT)
- HTML templates + HTMX
- Django static files
- SQLite for development (PostgreSQL-ready configuration exists)

## Local Development Setup

1. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create environment file (if needed):

```bash
cp .env.example .env
```

4. Run migrations:

```bash
python manage.py migrate
```

5. Create a superuser:

```bash
python manage.py createsuperuser
```

6. Run the development server:

```bash
python manage.py runserver 0.0.0.0:8008
```

Access the app at:

- `http://127.0.0.1:8008/`
- `http://0.0.0.0:8008/`

## One-Command Runner

Use the project script to prepare and run ScanOps:

```bash
./scripts/deploy_and_run.sh --mode local
```

Useful variants:

```bash
./scripts/deploy_and_run.sh --mode local --skip-install
./scripts/deploy_and_run.sh --mode local --seed-demo
./scripts/deploy_and_run.sh --mode local --no-run
```

## Project Layout (High Level)

- `apps/` modular Django apps (accounts, targets, scans, reports, schedules, notifications, assets, ops, etc.)
- `core/templates/` shared templates, pages, partials
- `core/static/scanops/css/app.css` shared ScanOps UI styles
- `core/settings/` environment-specific settings (`base.py`, `dev.py`, `production.py`)
- `Dockerfile`, `docker-compose.yml` container runtime

## Security Note

ScanOps is intended for internal authorized-use operations only.  
Do not use this project to scan unauthorized systems or networks.
