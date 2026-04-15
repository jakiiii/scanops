from __future__ import annotations

from collections import defaultdict

from django.conf import settings
from django.utils import timezone

from apps.ops.models import WorkerStatusSnapshot
from apps.scans.models import ScanExecution


def _determine_status(heartbeat_at, failed_jobs_count: int) -> str:
    if heartbeat_at is None:
        return WorkerStatusSnapshot.Status.OFFLINE
    age = timezone.now() - heartbeat_at
    if age > timezone.timedelta(minutes=20):
        return WorkerStatusSnapshot.Status.OFFLINE
    if age > timezone.timedelta(minutes=7) or failed_jobs_count > 3:
        return WorkerStatusSnapshot.Status.DEGRADED
    return WorkerStatusSnapshot.Status.ONLINE


def _build_worker_rows_from_runtime() -> list[dict]:
    rows: list[dict] = []
    runtime_qs = (
        ScanExecution.objects.exclude(worker_name="")
        .values("worker_name")
        .annotate()
    )
    if not runtime_qs:
        if settings.DEBUG:
            now = timezone.now()
            return [
                {
                    "worker_name": "worker-alpha",
                    "status": WorkerStatusSnapshot.Status.ONLINE,
                    "active_jobs_count": 3,
                    "queued_jobs_count": 4,
                    "failed_jobs_count": 0,
                    "heartbeat_at": now - timezone.timedelta(seconds=25),
                    "metadata_json": {"source": "dev-sample"},
                },
                {
                    "worker_name": "worker-bravo",
                    "status": WorkerStatusSnapshot.Status.DEGRADED,
                    "active_jobs_count": 1,
                    "queued_jobs_count": 6,
                    "failed_jobs_count": 2,
                    "heartbeat_at": now - timezone.timedelta(minutes=8),
                    "metadata_json": {"source": "dev-sample"},
                },
                {
                    "worker_name": "worker-charlie",
                    "status": WorkerStatusSnapshot.Status.OFFLINE,
                    "active_jobs_count": 0,
                    "queued_jobs_count": 0,
                    "failed_jobs_count": 4,
                    "heartbeat_at": now - timezone.timedelta(minutes=55),
                    "metadata_json": {"source": "dev-sample"},
                },
            ]
        return []

    grouped: dict[str, dict] = defaultdict(
        lambda: {
            "active_jobs_count": 0,
            "queued_jobs_count": 0,
            "failed_jobs_count": 0,
            "heartbeat_at": None,
        }
    )
    executions = ScanExecution.objects.exclude(worker_name="").order_by("-updated_at")[:500]
    for execution in executions:
        worker_bucket = grouped[execution.worker_name]
        if execution.status == ScanExecution.Status.RUNNING:
            worker_bucket["active_jobs_count"] += 1
        if execution.status == ScanExecution.Status.QUEUED:
            worker_bucket["queued_jobs_count"] += 1
        if execution.status == ScanExecution.Status.FAILED:
            worker_bucket["failed_jobs_count"] += 1
        if worker_bucket["heartbeat_at"] is None or execution.updated_at > worker_bucket["heartbeat_at"]:
            worker_bucket["heartbeat_at"] = execution.updated_at

    for worker_name, bucket in grouped.items():
        rows.append(
            {
                "worker_name": worker_name,
                "status": _determine_status(bucket["heartbeat_at"], bucket["failed_jobs_count"]),
                "active_jobs_count": bucket["active_jobs_count"],
                "queued_jobs_count": bucket["queued_jobs_count"],
                "failed_jobs_count": bucket["failed_jobs_count"],
                "heartbeat_at": bucket["heartbeat_at"] or timezone.now(),
                "metadata_json": {"source": "runtime"},
            }
        )
    return rows


def _latest_snapshots() -> list[WorkerStatusSnapshot]:
    snapshots = WorkerStatusSnapshot.objects.order_by("worker_name", "-created_at")
    latest_by_worker: dict[str, WorkerStatusSnapshot] = {}
    for snapshot in snapshots:
        if snapshot.worker_name not in latest_by_worker:
            latest_by_worker[snapshot.worker_name] = snapshot
    return list(latest_by_worker.values())


def collect_worker_dashboard_context(*, persist: bool = True) -> dict:
    snapshots = _latest_snapshots()
    if not snapshots:
        runtime_rows = _build_worker_rows_from_runtime()
        if persist and runtime_rows:
            created = [
                WorkerStatusSnapshot.objects.create(**row)
                for row in runtime_rows
            ]
            snapshots = created
        else:
            # create in-memory objects for display only
            snapshots = [WorkerStatusSnapshot(**row) for row in runtime_rows]

    total = len(snapshots)
    online = sum(1 for row in snapshots if row.status == WorkerStatusSnapshot.Status.ONLINE)
    degraded = sum(1 for row in snapshots if row.status == WorkerStatusSnapshot.Status.DEGRADED)
    offline = sum(1 for row in snapshots if row.status == WorkerStatusSnapshot.Status.OFFLINE)

    active_jobs = sum(int(row.active_jobs_count) for row in snapshots)
    queued_jobs = sum(int(row.queued_jobs_count) for row in snapshots)
    failed_jobs = sum(int(row.failed_jobs_count) for row in snapshots)
    checked_at = max((row.heartbeat_at for row in snapshots), default=timezone.now())

    return {
        "summary": {
            "total_workers": total,
            "online_workers": online,
            "degraded_workers": degraded,
            "offline_workers": offline,
            "active_jobs": active_jobs,
            "queue_backlog": queued_jobs,
            "failed_jobs": failed_jobs,
        },
        "workers": sorted(snapshots, key=lambda row: row.worker_name.lower()),
        "checked_at": checked_at,
    }
