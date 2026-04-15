from __future__ import annotations

from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.scans.models import ScanRequest
from apps.targets.models import Target


def build_dashboard_context() -> dict:
    now = timezone.now()
    seven_days_ago = now - timedelta(days=6)

    total_targets = Target.objects.count()
    total_scan_requests = ScanRequest.objects.count()
    pending_scan_requests = ScanRequest.objects.filter(status=ScanRequest.Status.PENDING).count()
    validated_scan_requests = ScanRequest.objects.filter(status=ScanRequest.Status.VALIDATED).count()

    recent_targets = Target.objects.select_related("owner", "created_by").order_by("-created_at")[:5]
    recent_scan_requests = (
        ScanRequest.objects.select_related("target", "requested_by", "profile")
        .order_by("-requested_at")[:5]
    )

    status_counts = {
        entry["status"]: entry["total"]
        for entry in ScanRequest.objects.values("status").annotate(total=Count("id"))
    }
    activity_summary = [
        {"label": "Draft", "count": status_counts.get(ScanRequest.Status.DRAFT, 0)},
        {"label": "Pending", "count": status_counts.get(ScanRequest.Status.PENDING, 0)},
        {"label": "Validated", "count": status_counts.get(ScanRequest.Status.VALIDATED, 0)},
        {"label": "Rejected", "count": status_counts.get(ScanRequest.Status.REJECTED, 0)},
    ]

    daily_scan_rows = (
        ScanRequest.objects.filter(requested_at__gte=seven_days_ago)
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
        "total_targets": total_targets,
        "total_scan_requests": total_scan_requests,
        "pending_scan_requests": pending_scan_requests,
        "validated_scan_requests": validated_scan_requests,
        "recent_targets": recent_targets,
        "recent_scan_requests": recent_scan_requests,
        "activity_summary": activity_summary,
        "daily_scan_labels": daily_scan_labels,
        "daily_scan_values": daily_scan_values,
        "chart_points": chart_points,
    }
