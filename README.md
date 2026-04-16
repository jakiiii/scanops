# ScanOps

ScanOps is an internal authorized-use network/security operations platform built with Django MVT, HTML templates, and HTMX.

## Stack

- Django 4.2 (MVT)
- HTMX + server-rendered templates
- Gunicorn in Docker
- PostgreSQL in Docker (default runtime database)

## Quick Docker Deploy (Local or VPS)

1. Ensure Docker Engine + Docker Compose plugin are installed.
2. Create runtime env file once:

```bash
cp .env.example .env
```

3. Update at least:
   - `JTRO_SECRET_KEY`
   - `SCANOPS_DB_PASSWORD`
   - `JTRO_ALLOWED_HOSTS` (for VPS/public hostnames)

4. Deploy:

```bash
./scripts/deploy_and_run.sh up
```

Access:

- `http://127.0.0.1:8008/login/`
- `http://0.0.0.0:8008/login/`

## Docker Operations

```bash
./scripts/deploy_and_run.sh ps
./scripts/deploy_and_run.sh logs
./scripts/deploy_and_run.sh restart
./scripts/deploy_and_run.sh down
```

## Database Migration Helpers

Create a backup from your currently configured local DB (`.env`):

```bash
./scripts/deploy_and_run.sh backup-local-db
```

Restore a SQL backup into Docker PostgreSQL:

```bash
./scripts/deploy_and_run.sh restore-db --backup-file dbbackup/migration/<your-backup>.sql
```

You can also restore automatically during startup:

```bash
./scripts/deploy_and_run.sh up --restore-db --backup-file dbbackup/migration/<your-backup>.sql
```

## Local Non-Docker Development (Optional)

You can still run Django directly:

```bash
python manage.py migrate
python manage.py runserver 0.0.0.0:8008
```

## Docs

- Docker workflow: `DOCKER_README.md`
- Backup scheduler and restore notes: `BACKUP_README.md`

## Security Note

ScanOps is intended for internal authorized-use operations only. Do not use this project to scan unauthorized systems or networks.
