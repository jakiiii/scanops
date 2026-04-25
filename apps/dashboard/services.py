from __future__ import annotations

from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.assets.models import Asset
from apps.notifications.models import Notification
from apps.ops.services import data_visibility_service
from apps.reports.models import GeneratedReport
from apps.scans.models import ScanExecution
from apps.scans.models import ScanRequest
from apps.schedules.models import ScanSchedule
from apps.targets.models import Target


def build_dashboard_context(user=None) -> dict:
    now = timezone.now()
    seven_days_ago = now - timedelta(days=6)
    can_view_all = data_visibility_service.user_can_view_all_data(user) if user is not None else False
    scope_label = "All" if can_view_all else "My"

    targets_qs = Target.objects.all()
    scan_requests_qs = ScanRequest.objects.all()
    executions_qs = ScanExecution.objects.filter(is_archived=False)
    reports_qs = GeneratedReport.objects.all()
    schedules_qs = ScanSchedule.objects.all()
    notifications_qs = Notification.objects.filter(is_read=False)
    assets_qs = Asset.objects.all()

    if user is not None:
        targets_qs = data_visibility_service.get_user_visible_targets(user, queryset=targets_qs)
        scan_requests_qs = data_visibility_service.get_user_visible_scan_requests(user, queryset=scan_requests_qs)
        executions_qs = data_visibility_service.get_user_visible_executions(user, queryset=executions_qs)
        reports_qs = data_visibility_service.get_user_visible_reports(user, queryset=reports_qs)
        schedules_qs = data_visibility_service.get_user_visible_schedules(user, queryset=schedules_qs)
        notifications_qs = data_visibility_service.get_user_visible_notifications(user, queryset=notifications_qs)
        assets_qs = data_visibility_service.get_user_visible_assets(user, queryset=assets_qs)

    total_targets = targets_qs.count()
    total_scan_requests = scan_requests_qs.count()
    pending_scan_requests = scan_requests_qs.filter(status=ScanRequest.Status.PENDING).count()
    validated_scan_requests = scan_requests_qs.filter(status=ScanRequest.Status.VALIDATED).count()
    running_scans = executions_qs.filter(status=ScanExecution.Status.RUNNING).count()
    completed_scans = executions_qs.filter(status=ScanExecution.Status.COMPLETED).count()
    failed_scans = executions_qs.filter(status=ScanExecution.Status.FAILED).count()
    total_reports = reports_qs.count()
    unread_notifications = notifications_qs.count()
    total_assets = assets_qs.count()
    total_schedules = schedules_qs.count()

    recent_targets = targets_qs.select_related("owner", "created_by").order_by("-created_at")[:5]
    recent_scan_requests = (
        scan_requests_qs.select_related("target", "requested_by", "profile")
        .order_by("-requested_at")[:5]
    )
    recent_executions = executions_qs.select_related("scan_request__target").order_by("-created_at")[:5]

    status_counts = {
        entry["status"]: entry["total"]
        for entry in scan_requests_qs.values("status").annotate(total=Count("id"))
    }
    activity_summary = [
        {"label": "Draft", "count": status_counts.get(ScanRequest.Status.DRAFT, 0)},
        {"label": "Pending", "count": status_counts.get(ScanRequest.Status.PENDING, 0)},
        {"label": "Validated", "count": status_counts.get(ScanRequest.Status.VALIDATED, 0)},
        {"label": "Rejected", "count": status_counts.get(ScanRequest.Status.REJECTED, 0)},
    ]

    daily_scan_rows = (
        scan_requests_qs.filter(requested_at__gte=seven_days_ago)
        .annotate(day=TruncDate("requested_at"))
        .values("day")
        .annotate(total=Count("id"))
        .order_by("day")
    )
    day_map = {row["day"]: row["total"] for row in daily_scan_rows}
    daily_scan_labels = []
    daily_scan_values = []
    for offset in range(7):
        day = (seven_days_ago + timedelta(days=offset)).date()
        daily_scan_labels.append(day.strftime("%a"))
        daily_scan_values.append(day_map.get(day, 0))
    max_value = max(daily_scan_values) if daily_scan_values else 0
    chart_points = []
    for label, count in zip(daily_scan_labels, daily_scan_values):
        chart_points.append(
            {
                "label": label,
                "count": count,
                "height": 12 if max_value == 0 else max(12, int((count / max_value) * 100)),
            }
        )

    return {
        "scope_label": scope_label,
        "can_view_all_data": can_view_all,
        "total_targets": total_targets,
        "total_scan_requests": total_scan_requests,
        "pending_scan_requests": pending_scan_requests,
        "validated_scan_requests": validated_scan_requests,
        "running_scans": running_scans,
        "completed_scans": completed_scans,
        "failed_scans": failed_scans,
        "total_reports": total_reports,
        "unread_notifications": unread_notifications,
        "total_assets": total_assets,
        "total_schedules": total_schedules,
        "recent_targets": recent_targets,
        "recent_scan_requests": recent_scan_requests,
        "recent_executions": recent_executions,
        "activity_summary": activity_summary,
        "daily_scan_labels": daily_scan_labels,
        "daily_scan_values": daily_scan_values,
        "chart_points": chart_points,
    }
