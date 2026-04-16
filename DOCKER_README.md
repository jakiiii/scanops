# ScanOps Docker Deployment Guide

This project is Dockerized with two runtime services:

- `scanops-web` (Django + Gunicorn)
- `db` (PostgreSQL 16)

The app is exposed on host port `8008`:

- `http://127.0.0.1:8008/login/`
- `http://0.0.0.0:8008/login/`

## Prerequisites

- Docker Engine
- Docker Compose plugin (`docker compose`)

## Environment Setup

Create `.env` once:

```bash
cp .env.example .env
```

Minimum values to review:

- `JTRO_SECRET_KEY`
- `JTRO_ALLOWED_HOSTS`
- `SCANOPS_DB_NAME`
- `SCANOPS_DB_USER`
- `SCANOPS_DB_PASSWORD`
- `SCANOPS_DB_PORT` (default `5432`)

## Deployment Script

Primary script:

```bash
./scripts/deploy_and_run.sh
```

Default behavior of `up`:

1. Builds `scanops-web` image.
2. Starts PostgreSQL (`db`) and app (`scanops-web`).
3. Waits for PostgreSQL readiness.
4. Lets the app entrypoint run `migrate` and `collectstatic`.
5. Verifies HTTP readiness at `127.0.0.1:8008/login/`.

### Common Commands

```bash
./scripts/deploy_and_run.sh up
./scripts/deploy_and_run.sh up --no-build
./scripts/deploy_and_run.sh restart
./scripts/deploy_and_run.sh down
./scripts/deploy_and_run.sh ps
./scripts/deploy_and_run.sh logs
./scripts/deploy_and_run.sh migrate
./scripts/deploy_and_run.sh collectstatic
./scripts/deploy_and_run.sh check
```

### Port Override

```bash
SCANOPS_PORT=8010 ./scripts/deploy_and_run.sh up
```

### DB Backup and Restore

Backup current local DB defined by `.env`:

```bash
./scripts/deploy_and_run.sh backup-local-db
```

This writes backup files to:

```text
dbbackup/migration/
```

Restore into Docker PostgreSQL:

```bash
./scripts/deploy_and_run.sh restore-db --backup-file dbbackup/migration/<backup-file>.sql
```

Restore during startup:

```bash
./scripts/deploy_and_run.sh up --restore-db --backup-file dbbackup/migration/<backup-file>.sql
```

## Direct Docker Compose (Without Script)

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f --tail=200
docker compose down
```

## Persistence

Named volumes:

- `scanops_postgres_data` (PostgreSQL data)
- `scanops_static` (collected static files)
- `scanops_media` (uploaded media)
- `scanops_logs` (application logs)

## Troubleshooting

- App not reachable:
  - `./scripts/deploy_and_run.sh logs`
- DB container unhealthy:
  - `docker compose logs db`
- Fresh reset (removes all persisted Docker DB/static/media data):
  - `docker compose down -v`
