# ScanOps Docker Guide

This setup runs ScanOps on:

- `0.0.0.0:8008`

The container entrypoint automatically runs:

1. `python manage.py migrate`
2. `python manage.py collectstatic --noinput`
3. Gunicorn bound to `0.0.0.0:8008`

## Option 1: Docker Compose (Recommended)

From project root:

```bash
docker compose build
docker compose up -d
```

Check status:

```bash
docker compose ps
docker compose logs -f --tail=200
```

Open:

- `http://127.0.0.1:8008/login/`
- `http://0.0.0.0:8008/login/`

Stop:

```bash
docker compose down
```

## Using Project Script (Docker Mode)

The repository includes a unified runner script:

```bash
./scripts/deploy_and_run.sh --mode docker
```

Useful variants:

```bash
./scripts/deploy_and_run.sh --mode docker --no-build
./scripts/deploy_and_run.sh --mode docker --logs
./scripts/deploy_and_run.sh --mode docker --no-run
```

## Option 2: Plain Docker

Build image:

```bash
docker build -t scanops:latest .
```

Run container on port `8008`:

```bash
docker run --rm -p 8008:8008 \
  -e JTRO_ENVIRONMENT=dev \
  -e JTRO_DEBUG=True \
  -e JTRO_SECRET_KEY=scanops-dev-secret-key-change-me \
  -e JTRO_ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0 \
  -e JTRO_DEV_DATABASE=sqlite \
  -e JTRO_SQLITE_PATH=/app/state/db.sqlite3 \
  -e JTRO_SSL_ENABLED=False \
  -v scanops_state:/app/state \
  -v scanops_static:/app/static_root \
  -v scanops_media:/app/media_root \
  scanops:latest
```

## Useful Commands

Run one-off migration inside compose service:

```bash
docker compose run --rm scanops-web python manage.py migrate
```

Create superuser inside compose service:

```bash
docker compose run --rm scanops-web python manage.py createsuperuser
```

## Troubleshooting

- Port already in use:
  - Change host mapping in `docker-compose.yml` (left side of `8008:8008`) or stop the process using port `8008`.
- App does not start:
  - Check logs: `docker compose logs --tail=200`.
- Host access issues:
  - Ensure `JTRO_ALLOWED_HOSTS` includes the host you use (already set to `localhost,127.0.0.1,0.0.0.0` in compose).
- Fresh reset:
  - `docker compose down -v` to remove containers + named volumes and recreate from scratch.
