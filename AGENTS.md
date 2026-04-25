# AGENTS.md

## Project snapshot
- `ScanOps` is a Django 4.2 MVT app for internal, authorized-use security operations.
- UI is server-rendered templates + HTMX; most work lives in `apps/*/views.py`, not in a separate frontend.
- The root URL config is `core/urls.py`, which mounts `apis.urls` and app namespaces like `accounts`, `dashboard`, `scans`, `reports`, `schedules`, `notifications`, `assets`, and `ops`.

## Runtime and settings
- `manage.py` always calls `core.env.configure_environment()` first; environment selection is driven by `JTRO_ENVIRONMENT`.
- `core/env.py` loads `.env.local` before `.env` unless skipped, then selects `core.settings.dev` or `core.settings.production`.
- Production settings require explicit `JTRO_SECRET_KEY` and `JTRO_ALLOWED_HOSTS`; `core/settings/base.py` applies security headers, Axes, and CSP-related middleware.
- Custom user/auth behavior is in `apps/accounts/models/user_models.py` and `apps/accounts/forms/auth.py`.

## Architecture patterns to follow
- Use the service layer for cross-cutting logic: e.g. `apps/ops/services/permission_service.py`, `apps/ops/services/app_settings_service.py`, `apps/dashboard/services.py`.
- RBAC is role-based through `apps/ops/models.py` + `apps/ops/rbac.py`; scope queryset access with `scope_queryset_for_user(...)` instead of ad hoc filters.
- HTMX requests usually return partial templates; see `apps/ops/views.py` (`partials/*.html`) and `apps/scans/urls.py` for the pattern.
- Keep admin/policy changes auditable: `apps/ops/views.py` logs via `log_admin_action(...)` and settings updates go through `app_settings_service`.

## Representative conventions
- Settings forms map to `AppSetting.Category` values; examples: `GeneralSettingsForm`, `ScanPolicySettingsForm`, `AllowedTargetsSettingsForm` in `apps/ops/forms.py`.
- Seed/maintenance commands are first-class workflows: `apps/core/management/commands/seed_demo_environment.py`, `apps/scans/management/commands/seed_scan_runtime.py`, `apps/ops/management/commands/sync_role_permissions.py`.
- Authentication flows log both success and failure, e.g. `apps/accounts/views.py` writes user logs on login/logout.

## Commands agents should prefer
```bash
./scripts/deploy_and_run.sh up
./scripts/deploy_and_run.sh check
./scripts/deploy_and_run.sh migrate
./scripts/deploy_and_run.sh collectstatic
python manage.py check
python manage.py test
```

## Deployment and data ops
- Docker is the default runtime: `docker-compose.yml` defines `db` (PostgreSQL 16) and `scanops-web` (Gunicorn on port 8008).
- Use `./scripts/deploy_and_run.sh backup-local-db` and `restore-db` for DB migration work; backup generation lives in `scripts/backup_db.py`.
- The project writes logs to `app_logs/` and collected assets/media to `static_root/` and `media_root/`.

## Guardrails
- Keep changes consistent with the existing module layout and template-driven UI; avoid introducing a parallel API-first architecture unless the request explicitly needs it.
- Respect the internal-use/security scope noted in `README.md`; do not add features that assume unauthorized scanning.
- When changing permissions, settings, or target-scope logic, update the service layer and the corresponding management command/seed path together.

