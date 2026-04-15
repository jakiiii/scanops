from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.scans.models import ScanEventLog, ScanExecution, ScanRequest


def _priority_from_request(scan_request: ScanRequest) -> int:
    if scan_request.timing_profile == "fast":
        return 1
    if scan_request.timing_profile == "balanced":
        return 2
    return 3


def log_execution_event(
    execution: ScanExecution,
    event_type: str,
    message: str,
    metadata: dict | None = None,
) -> ScanEventLog:
    return ScanEventLog.objects.create(
        execution=execution,
        event_type=event_type,
        message=message,
        metadata_json=metadata or {},
    )


@transaction.atomic
def create_execution_from_request(
    scan_request: ScanRequest,
    *,
    priority: int | None = None,
    status_message: str = "Queued for worker assignment.",
) -> ScanExecution:
    execution = ScanExecution.objects.create(
        scan_request=scan_request,
        status=ScanExecution.Status.QUEUED,
        queue_status=ScanExecution.QueueStatus.WAITING,
        progress_percent=0,
        current_stage="Queued",
        status_message=status_message,
        priority=priority or _priority_from_request(scan_request),
    )
    if scan_request.status == ScanRequest.Status.DRAFT:
        scan_request.status = ScanRequest.Status.PENDING
        scan_request.save(update_fields=["status", "updated_at"])
    log_execution_event(
        execution,
        "queued",
        f"Execution queued from scan request #{scan_request.pk}.",
    )
    return execution


def ensure_executions_for_ready_requests(limit: int = 50) -> int:
    ready_requests = (
        ScanRequest.objects.filter(
            Q(status=ScanRequest.Status.PENDING) | Q(status=ScanRequest.Status.VALIDATED)
        )
        .exclude(executions__isnull=False)
        .select_related("target", "profile")
        .order_by("-requested_at")[:limit]
    )
    created_count = 0
    for request in ready_requests:
        create_execution_from_request(request)
        created_count += 1
    return created_count


def assign_execution(execution: ScanExecution, worker_name: str) -> ScanExecution:
    execution.worker_name = worker_name
    execution.queue_status = ScanExecution.QueueStatus.ASSIGNED
    execution.status_message = f"Assigned to worker {worker_name}."
    execution.save(update_fields=["worker_name", "queue_status", "status_message", "updated_at"])
    log_execution_event(execution, "assigned", execution.status_message)
    return execution


def start_execution(execution: ScanExecution, worker_name: str | None = None) -> ScanExecution:
    now = timezone.now()
    execution.status = ScanExecution.Status.RUNNING
    execution.queue_status = ScanExecution.QueueStatus.PROCESSING
    execution.started_at = execution.started_at or now
    execution.current_stage = "Host Discovery"
    execution.status_message = "Execution started and host discovery is running."
    execution.progress_percent = max(execution.progress_percent, 3)
    if worker_name:
        execution.worker_name = worker_name
    execution.save(
        update_fields=[
            "status",
            "queue_status",
            "started_at",
            "current_stage",
            "status_message",
            "progress_percent",
            "worker_name",
            "updated_at",
        ]
    )
    log_execution_event(execution, "started", execution.status_message)
    return execution


def update_execution_progress(
    execution: ScanExecution,
    *,
    progress_percent: int,
    stage: str,
    message: str,
) -> ScanExecution:
    execution.status = ScanExecution.Status.RUNNING
    execution.queue_status = ScanExecution.QueueStatus.PROCESSING
    execution.progress_percent = max(0, min(progress_percent, 99))
    execution.current_stage = stage
    execution.status_message = message
    if execution.started_at:
        execution.duration_seconds = int((timezone.now() - execution.started_at).total_seconds())
    execution.save(
        update_fields=[
            "status",
            "queue_status",
            "progress_percent",
            "current_stage",
            "status_message",
            "duration_seconds",
            "updated_at",
        ]
    )
    log_execution_event(
        execution,
        "progress",
        message,
        metadata={"progress_percent": execution.progress_percent, "stage": stage},
    )
    return execution


def _complete_execution(
    execution: ScanExecution,
    *,
    status: str,
    queue_status: str,
    message: str,
    progress: int,
) -> ScanExecution:
    now = timezone.now()
    execution.status = status
    execution.queue_status = queue_status
    execution.completed_at = now
    execution.progress_percent = progress
    execution.current_stage = "Completed" if status == ScanExecution.Status.COMPLETED else "Terminated"
    execution.status_message = message
    if execution.started_at:
        execution.duration_seconds = int((now - execution.started_at).total_seconds())
    execution.save(
        update_fields=[
            "status",
            "queue_status",
            "completed_at",
            "progress_percent",
            "current_stage",
            "status_message",
            "duration_seconds",
            "updated_at",
        ]
    )
    return execution


def complete_execution(execution: ScanExecution, message: str = "Execution completed successfully.") -> ScanExecution:
    execution = _complete_execution(
        execution,
        status=ScanExecution.Status.COMPLETED,
        queue_status=ScanExecution.QueueStatus.DONE,
        message=message,
        progress=100,
    )
    log_execution_event(execution, "completed", message)
    return execution


def fail_execution(execution: ScanExecution, message: str = "Execution failed.") -> ScanExecution:
    execution = _complete_execution(
        execution,
        status=ScanExecution.Status.FAILED,
        queue_status=ScanExecution.QueueStatus.ERROR,
        message=message,
        progress=execution.progress_percent,
    )
    log_execution_event(execution, "failed", message)
    return execution


def cancel_execution(execution: ScanExecution, message: str = "Execution cancelled by operator.") -> ScanExecution:
    execution = _complete_execution(
        execution,
        status=ScanExecution.Status.CANCELLED,
        queue_status=ScanExecution.QueueStatus.ERROR,
        message=message,
        progress=execution.progress_percent,
    )
    log_execution_event(execution, "cancelled", message)
    return execution


def archive_execution(execution: ScanExecution) -> ScanExecution:
    execution.is_archived = True
    execution.save(update_fields=["is_archived", "updated_at"])
    log_execution_event(execution, "archived", "Execution archived.")
    return execution


def restore_execution(execution: ScanExecution) -> ScanExecution:
    execution.is_archived = False
    execution.save(update_fields=["is_archived", "updated_at"])
    log_execution_event(execution, "restored", "Execution restored from archive.")
    return execution


def retry_execution(execution: ScanExecution) -> ScanExecution:
    return create_execution_from_request(
        execution.scan_request,
        priority=execution.priority,
        status_message=f"Retry queued from {execution.execution_id}.",
    )


def _stage_for_progress(progress: int) -> tuple[str, str]:
    if progress < 20:
        return "Host Discovery", "Discovering reachable hosts."
    if progress < 40:
        return "Port Scan", "Scanning top ports."
    if progress < 60:
        return "Service Detection", "Fingerprinting detected services."
    if progress < 80:
        return "Version Detection", "Collecting banner and version metadata."
    if progress < 95:
        return "Script Analysis", "Running safe script analysis."
    return "Finalizing", "Preparing final structured result."


def simulate_execution_tick(execution: ScanExecution) -> ScanExecution:
    """
    Development-only lifecycle simulation for UI testing. This intentionally
    avoids command execution and only updates model state.
    """
    if execution.status in {
        ScanExecution.Status.COMPLETED,
        ScanExecution.Status.FAILED,
        ScanExecution.Status.CANCELLED,
    }:
        return execution

    if execution.status == ScanExecution.Status.QUEUED:
        return start_execution(execution, worker_name=execution.worker_name or "worker-sim-01")

    if execution.status == ScanExecution.Status.RUNNING:
        started_at = execution.started_at or timezone.now()
        elapsed = timezone.now() - started_at
        elapsed_seconds = int(elapsed.total_seconds())
        increment = 4 + ((elapsed_seconds // 7) % 8)
        next_progress = min(100, execution.progress_percent + increment)
        stage, message = _stage_for_progress(next_progress)
        if next_progress >= 100:
            complete_execution(execution, "Execution completed (simulated).")
            from apps.scans.services.result_service import generate_mock_result_for_execution

            generate_mock_result_for_execution(execution, force=False)
            return execution
        return update_execution_progress(
            execution,
            progress_percent=next_progress,
            stage=stage,
            message=message,
        )

    return execution


def elapsed_time_display(execution: ScanExecution) -> str:
    if execution.started_at is None:
        return "00:00"
    elapsed = timezone.now() - execution.started_at
    if execution.completed_at:
        elapsed = execution.completed_at - execution.started_at
    total_seconds = max(0, int(elapsed.total_seconds()))
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"
