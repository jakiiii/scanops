from __future__ import annotations

import os
import shutil
from pathlib import Path

from django.conf import settings
from django.db import connection
from django.utils import timezone

from apps.ops.models import SystemHealthSnapshot
from apps.schedules.models import ScanSchedule
from apps.scans.models import ScanExecution


STATUS_WEIGHT = {
    SystemHealthSnapshot.Status.HEALTHY: 0,
    SystemHealthSnapshot.Status.UNKNOWN: 1,
    SystemHealthSnapshot.Status.WARNING: 2,
    SystemHealthSnapshot.Status.ERROR: 3,
}


def _db_check() -> tuple[str, str, dict]:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            row = cursor.fetchone()
        if row and row[0] == 1:
            return (SystemHealthSnapshot.Status.HEALTHY, "Database connection is healthy.", {})
        return (SystemHealthSnapshot.Status.WARNING, "Database returned unexpected probe value.", {})
    except Exception as exc:
        return (SystemHealthSnapshot.Status.ERROR, f"Database check failed: {exc}", {})


def _nmap_check() -> tuple[str, str, dict]:
    nmap_path = shutil.which("nmap")
    if nmap_path:
        return (
            SystemHealthSnapshot.Status.HEALTHY,
            f"Nmap binary detected at {nmap_path}.",
            {"path": nmap_path},
        )
    return (
        SystemHealthSnapshot.Status.WARNING,
        "Nmap binary not found in PATH.",
        {"path": None},
    )


def _queue_check() -> tuple[str, str, dict]:
    broker = os.environ.get("CELERY_BROKER_URL") or os.environ.get("RQ_REDIS_URL")
    queued_count = ScanExecution.objects.filter(status=ScanExecution.Status.QUEUED).count()
    if broker:
        if queued_count > 100:
            return (
                SystemHealthSnapshot.Status.WARNING,
                f"Queue configured; backlog is elevated ({queued_count} queued jobs).",
                {"queued_jobs": queued_count, "broker": "configured"},
            )
        return (
            SystemHealthSnapshot.Status.HEALTHY,
            "Queue configuration detected and backlog is within threshold.",
            {"queued_jobs": queued_count, "broker": "configured"},
        )
    if queued_count:
        return (
            SystemHealthSnapshot.Status.WARNING,
            f"No queue backend configured but {queued_count} queued jobs exist.",
            {"queued_jobs": queued_count, "broker": "missing"},
        )
    return (
        SystemHealthSnapshot.Status.UNKNOWN,
        "Queue backend is not configured.",
        {"queued_jobs": 0, "broker": "missing"},
    )


def _scheduler_check() -> tuple[str, str, dict]:
    enabled_count = ScanSchedule.objects.filter(is_enabled=True).count()
    if enabled_count == 0:
        return (
            SystemHealthSnapshot.Status.UNKNOWN,
            "No enabled schedules are configured.",
            {"enabled_schedules": 0},
        )
    overdue_count = ScanSchedule.objects.filter(
        is_enabled=True,
        next_run_at__isnull=False,
        next_run_at__lt=timezone.now() - timezone.timedelta(minutes=30),
    ).count()
    if overdue_count:
        return (
            SystemHealthSnapshot.Status.WARNING,
            f"Scheduler has {overdue_count} overdue run(s).",
            {"enabled_schedules": enabled_count, "overdue": overdue_count},
        )
    return (
        SystemHealthSnapshot.Status.HEALTHY,
        "Scheduler has enabled plans and no overdue runs.",
        {"enabled_schedules": enabled_count, "overdue": 0},
    )


def _storage_check() -> tuple[str, str, dict]:
    media_path = Path(settings.MEDIA_ROOT)
    static_path = Path(settings.STATIC_ROOT)
    media_ok = media_path.exists() and os.access(media_path, os.W_OK)
    static_ok = static_path.exists() and os.access(static_path, os.W_OK)

    if media_ok and static_ok:
        return (
            SystemHealthSnapshot.Status.HEALTHY,
            "Static and media storage paths are writable.",
            {"media": str(media_path), "static": str(static_path)},
        )
    if media_ok or static_ok:
        return (
            SystemHealthSnapshot.Status.WARNING,
            "One storage path is writable while another is not.",
            {"media_writable": media_ok, "static_writable": static_ok},
        )
    return (
        SystemHealthSnapshot.Status.ERROR,
        "Storage paths are not writable.",
        {"media_writable": media_ok, "static_writable": static_ok},
    )


def run_health_checks(*, persist: bool = True) -> list[dict]:
    checked_at = timezone.now()
    services: list[dict] = []

    services.append(
        {
            "service_name": SystemHealthSnapshot.ServiceName.DJANGO_APP,
            "status": SystemHealthSnapshot.Status.HEALTHY,
            "summary": "Django application process is responsive.",
            "metadata_json": {"debug": bool(settings.DEBUG)},
            "checked_at": checked_at,
        }
    )

    db_status, db_summary, db_meta = _db_check()
    services.append(
        {
            "service_name": SystemHealthSnapshot.ServiceName.DATABASE,
            "status": db_status,
            "summary": db_summary,
            "metadata_json": db_meta,
            "checked_at": checked_at,
        }
    )

    nmap_status, nmap_summary, nmap_meta = _nmap_check()
    services.append(
        {
            "service_name": SystemHealthSnapshot.ServiceName.NMAP_BINARY,
            "status": nmap_status,
            "summary": nmap_summary,
            "metadata_json": nmap_meta,
            "checked_at": checked_at,
        }
    )

    queue_status, queue_summary, queue_meta = _queue_check()
    services.append(
        {
            "service_name": SystemHealthSnapshot.ServiceName.QUEUE_SERVICE,
            "status": queue_status,
            "summary": queue_summary,
            "metadata_json": queue_meta,
            "checked_at": checked_at,
        }
    )

    scheduler_status, scheduler_summary, scheduler_meta = _scheduler_check()
    services.append(
        {
            "service_name": SystemHealthSnapshot.ServiceName.SCHEDULER,
            "status": scheduler_status,
            "summary": scheduler_summary,
            "metadata_json": scheduler_meta,
            "checked_at": checked_at,
        }
    )

    storage_status, storage_summary, storage_meta = _storage_check()
    services.append(
        {
            "service_name": SystemHealthSnapshot.ServiceName.STORAGE,
            "status": storage_status,
            "summary": storage_summary,
            "metadata_json": storage_meta,
            "checked_at": checked_at,
        }
    )

    if persist:
        for service in services:
            SystemHealthSnapshot.objects.create(
                service_name=service["service_name"],
                status=service["status"],
                summary=service["summary"],
                metadata_json=service["metadata_json"],
                checked_at=service["checked_at"],
            )
    return services


def overall_status(services: list[dict]) -> str:
    if not services:
        return SystemHealthSnapshot.Status.UNKNOWN
    return max(services, key=lambda row: STATUS_WEIGHT.get(row["status"], 0))["status"]


def recent_alerts(limit: int = 8):
    return SystemHealthSnapshot.objects.filter(
        status__in=[SystemHealthSnapshot.Status.WARNING, SystemHealthSnapshot.Status.ERROR]
    ).order_by("-checked_at")[:limit]


def recent_timeline(limit: int = 20):
    return SystemHealthSnapshot.objects.order_by("-checked_at")[:limit]
