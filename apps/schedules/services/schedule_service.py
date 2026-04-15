from __future__ import annotations

import re
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.scans.models import ScanRequest
from apps.scans.services.execution_service import create_execution_from_request
from apps.schedules.models import ScanSchedule, ScheduleRunLog


def _custom_delta(recurrence_rule: str) -> timedelta:
    rule = (recurrence_rule or "").strip().lower()
    match = re.fullmatch(r"(\d+)\s*([mhdw])", rule)
    if not match:
        return timedelta(days=1)
    value = int(match.group(1))
    unit = match.group(2)
    if unit == "m":
        return timedelta(minutes=value)
    if unit == "h":
        return timedelta(hours=value)
    if unit == "w":
        return timedelta(weeks=value)
    return timedelta(days=value)


def compute_next_run_at(schedule: ScanSchedule, *, reference_time=None) -> timezone.datetime | None:
    now = reference_time or timezone.now()
    if schedule.end_at and now >= schedule.end_at:
        return None

    if schedule.schedule_type == ScanSchedule.ScheduleType.ONE_TIME:
        if schedule.last_run_at:
            return None
        return schedule.start_at if schedule.start_at >= now else None

    base = schedule.last_run_at or schedule.start_at
    if base is None:
        base = now

    if schedule.schedule_type == ScanSchedule.ScheduleType.DAILY:
        step = timedelta(days=1)
    elif schedule.schedule_type == ScanSchedule.ScheduleType.WEEKLY:
        step = timedelta(weeks=1)
    elif schedule.schedule_type == ScanSchedule.ScheduleType.MONTHLY:
        step = timedelta(days=30)
    else:
        step = _custom_delta(schedule.recurrence_rule)

    candidate = base
    while candidate <= now:
        candidate = candidate + step

    if schedule.end_at and candidate > schedule.end_at:
        return None
    return candidate


def apply_next_run(schedule: ScanSchedule, *, save: bool = True) -> ScanSchedule:
    schedule.next_run_at = compute_next_run_at(schedule)
    if save:
        schedule.save(update_fields=["next_run_at", "updated_at"])
    return schedule


def build_schedule_summary(schedule: ScanSchedule) -> dict:
    return {
        "name": schedule.name,
        "target": schedule.target.target_value,
        "profile": schedule.profile.name if schedule.profile else schedule.get_scan_type_display(),
        "frequency": schedule.get_schedule_type_display(),
        "start_at": schedule.start_at,
        "end_at": schedule.end_at,
        "next_run_at": schedule.next_run_at,
        "timing_profile": schedule.get_timing_profile_display(),
        "notifications": schedule.notification_enabled,
    }


def _notify_schedule_event(schedule: ScanSchedule, *, title: str, message: str, severity: str = "info") -> None:
    if schedule.created_by is None:
        return
    from apps.notifications.services.notification_service import create_notification

    create_notification(
        recipient=schedule.created_by,
        title=title,
        message=message,
        notification_type="schedule_triggered",
        severity=severity,
        related_schedule=schedule,
        action_url=f"/schedules/{schedule.pk}/edit/",
    )


@transaction.atomic
def trigger_schedule_run(schedule: ScanSchedule, *, user=None) -> ScheduleRunLog:
    now = timezone.now()
    run_log = ScheduleRunLog.objects.create(
        schedule=schedule,
        run_at=now,
        status=ScheduleRunLog.Status.PENDING,
        message="Manual trigger requested.",
    )

    if not schedule.is_enabled:
        run_log.status = ScheduleRunLog.Status.SKIPPED
        run_log.message = "Schedule is disabled; run skipped."
        run_log.save(update_fields=["status", "message"])
        _notify_schedule_event(
            schedule,
            title=f"Schedule skipped: {schedule.name}",
            message=run_log.message,
            severity="warning",
        )
        return run_log

    try:
        request = ScanRequest.objects.create(
            target=schedule.target,
            profile=schedule.profile,
            scan_type=schedule.scan_type,
            port_input=schedule.port_input,
            enable_host_discovery=schedule.enable_host_discovery,
            enable_service_detection=schedule.enable_service_detection,
            enable_version_detection=schedule.enable_version_detection,
            enable_os_detection=schedule.enable_os_detection,
            enable_traceroute=schedule.enable_traceroute,
            enable_dns_resolution=schedule.enable_dns_resolution,
            timing_profile=schedule.timing_profile,
            status=ScanRequest.Status.PENDING,
            validation_summary="Triggered by schedule",
            notes=f"Triggered by schedule: {schedule.name}",
            requested_by=user or schedule.created_by,
        )
        execution = create_execution_from_request(
            request,
            status_message=f"Triggered from schedule {schedule.name}.",
        )
        run_log.execution = execution
        run_log.status = ScheduleRunLog.Status.COMPLETED
        run_log.message = f"Execution queued as {execution.execution_id}."
        run_log.save(update_fields=["execution", "status", "message"])

        schedule.last_run_at = now
        schedule.next_run_at = compute_next_run_at(schedule, reference_time=now)
        schedule.save(update_fields=["last_run_at", "next_run_at", "updated_at"])

        _notify_schedule_event(
            schedule,
            title=f"Schedule run queued: {schedule.name}",
            message=run_log.message,
            severity="success",
        )
    except Exception as exc:  # noqa: BLE001
        run_log.status = ScheduleRunLog.Status.FAILED
        run_log.message = f"Run failed: {exc}"
        run_log.save(update_fields=["status", "message"])
        _notify_schedule_event(
            schedule,
            title=f"Schedule failed: {schedule.name}",
            message=run_log.message,
            severity="error",
        )
    return run_log

