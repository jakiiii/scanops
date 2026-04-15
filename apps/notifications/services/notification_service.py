from __future__ import annotations

from typing import Iterable

from django.utils import timezone

from apps.notifications.models import Notification


def create_notification(
    *,
    recipient,
    title: str,
    message: str,
    notification_type: str,
    severity: str = Notification.Severity.INFO,
    related_execution=None,
    related_result=None,
    related_schedule=None,
    related_asset=None,
    action_url: str = "",
    metadata: dict | None = None,
) -> Notification:
    return Notification.objects.create(
        recipient=recipient,
        title=title,
        message=message,
        notification_type=notification_type,
        severity=severity,
        related_execution=related_execution,
        related_result=related_result,
        related_schedule=related_schedule,
        related_asset=related_asset,
        action_url=action_url,
        metadata_json=metadata or {},
    )


def mark_as_read(notification: Notification) -> Notification:
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=["is_read", "read_at"])
    return notification


def mark_as_unread(notification: Notification) -> Notification:
    if notification.is_read:
        notification.is_read = False
        notification.read_at = None
        notification.save(update_fields=["is_read", "read_at"])
    return notification


def bulk_mark_read(notifications: Iterable[Notification]) -> int:
    ids = [item.pk for item in notifications]
    if not ids:
        return 0
    return Notification.objects.filter(pk__in=ids, is_read=False).update(
        is_read=True,
        read_at=timezone.now(),
    )


def bulk_mark_unread(notifications: Iterable[Notification]) -> int:
    ids = [item.pk for item in notifications]
    if not ids:
        return 0
    return Notification.objects.filter(pk__in=ids, is_read=True).update(
        is_read=False,
        read_at=None,
    )


def notify_report_generated(report) -> Notification | None:
    if report.generated_by is None:
        return None
    return create_notification(
        recipient=report.generated_by,
        title=f"Report ready: {report.title}",
        message=f"{report.get_report_type_display()} generated in {report.get_format_display()} format.",
        notification_type=Notification.NotificationType.REPORT_GENERATED,
        severity=Notification.Severity.SUCCESS,
        related_execution=report.source_execution,
        related_result=report.source_result,
        related_asset=report.asset,
        action_url=f"/reports/{report.pk}/",
        metadata={"report_id": report.pk, "status": report.status},
    )


def notify_asset_changed(*, asset, summary: str, recipient=None) -> Notification | None:
    if recipient is None:
        return None
    return create_notification(
        recipient=recipient,
        title=f"Asset change detected: {asset.name}",
        message=summary,
        notification_type=Notification.NotificationType.ASSET_CHANGED,
        severity=Notification.Severity.WARNING,
        related_asset=asset,
        action_url=f"/assets/{asset.pk}/changes/",
    )

