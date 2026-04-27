from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any

from django.core.paginator import Paginator
from django.db.models import Count, Max, Q, Value
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from apps.accounts.models import UserLogs


def _start_of_day(day):
    tz = timezone.get_current_timezone()
    return timezone.make_aware(datetime.combine(day, time.min), tz)


def _resolve_period_bounds(filters: dict[str, Any]) -> tuple[Any | None, Any | None]:
    today = timezone.localdate()
    period = (filters.get("period") or "").strip()

    if period == "today":
        return today, today
    if period == "yesterday":
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday
    if period == "this_week":
        week_start = today - timedelta(days=today.weekday())
        return week_start, today
    if period == "this_month":
        return today.replace(day=1), today
    if period == "this_year":
        return today.replace(month=1, day=1), today
    if period == "custom":
        return filters.get("start_date"), filters.get("end_date")
    return None, None


def _apply_date_bounds(queryset, *, start_date=None, end_date=None):
    if start_date:
        queryset = queryset.filter(action_datetime__gte=_start_of_day(start_date))
    if end_date:
        queryset = queryset.filter(action_datetime__lt=_start_of_day(end_date + timedelta(days=1)))
    return queryset


def _apply_filters(queryset, filters: dict[str, Any], *, include_period: bool):
    username = (filters.get("username") or "").strip()
    if username:
        queryset = queryset.filter(
            Q(username_snapshot__icontains=username)
            | Q(user__username__icontains=username)
            | Q(user__email__icontains=username)
        )

    action_type = (filters.get("action_type") or "").strip()
    if action_type:
        queryset = queryset.filter(action_type=action_type)

    result = (filters.get("result") or "").strip()
    if result == "success":
        queryset = queryset.filter(is_success=True)
    elif result == "failed":
        queryset = queryset.filter(is_success=False)

    ip_contains = (filters.get("ip_contains") or "").strip()
    if ip_contains:
        queryset = queryset.filter(ip_address__icontains=ip_contains)

    path_contains = (filters.get("path_contains") or "").strip()
    if path_contains:
        queryset = queryset.filter(path__icontains=path_contains)

    actor_type = (filters.get("actor_type") or "").strip()
    if actor_type == "authenticated":
        queryset = queryset.filter(user__isnull=False)
    elif actor_type == "anonymous":
        queryset = queryset.filter(user__isnull=True)

    if include_period:
        start_date, end_date = _resolve_period_bounds(filters)
        queryset = _apply_date_bounds(queryset, start_date=start_date, end_date=end_date)

    return queryset


def _build_daily_trend(base_queryset, filters: dict[str, Any]) -> list[dict[str, Any]]:
    trend_start, trend_end = _resolve_period_bounds(filters)
    today = timezone.localdate()

    if trend_end is None:
        trend_end = today
    if trend_start is None:
        trend_start = trend_end - timedelta(days=13)

    if trend_start > trend_end:
        trend_start, trend_end = trend_end, trend_start

    trend_queryset = _apply_date_bounds(base_queryset, start_date=trend_start, end_date=trend_end)
    aggregated = (
        trend_queryset.annotate(day=TruncDate("action_datetime", tzinfo=timezone.get_current_timezone()))
        .values("day")
        .annotate(
            total_logs=Count("id"),
            success_count=Count("id", filter=Q(is_success=True)),
            failure_count=Count("id", filter=Q(is_success=False)),
        )
        .order_by("day")
    )
    day_map = {item["day"]: item for item in aggregated}

    trend_rows: list[dict[str, Any]] = []
    current = trend_start
    while current <= trend_end:
        row = day_map.get(current)
        trend_rows.append(
            {
                "date": current,
                "total_logs": (row or {}).get("total_logs", 0),
                "success_count": (row or {}).get("success_count", 0),
                "failure_count": (row or {}).get("failure_count", 0),
            }
        )
        current += timedelta(days=1)
    return trend_rows


def _querystring_without_page(query_params) -> str:
    if query_params is None:
        return ""
    params = query_params.copy()
    if "page" in params:
        params.pop("page")
    return params.urlencode()


def build_user_logs_analytics_payload(
    *,
    filters: dict[str, Any] | None = None,
    page_number: int | str | None = None,
    query_params=None,
    page_size: int = 20,
) -> dict[str, Any]:
    filters = filters or {}
    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    base_queryset = _apply_filters(UserLogs.objects.select_related("user"), filters, include_period=False)
    filtered_queryset = _apply_filters(base_queryset, filters, include_period=True).order_by("-action_datetime", "-id")

    summary = filtered_queryset.aggregate(
        total_logs=Count("id"),
        successful_actions=Count("id", filter=Q(is_success=True)),
        failed_actions=Count("id", filter=Q(is_success=False)),
        unique_users=Count("username_snapshot", distinct=True, filter=~Q(username_snapshot="")),
        unique_ips=Count("ip_address", distinct=True, filter=~Q(ip_address="")),
        login_count=Count("id", filter=Q(action_type=UserLogs.ActionType.LOGIN)),
        logout_count=Count("id", filter=Q(action_type=UserLogs.ActionType.LOGOUT)),
    )

    summary.update(
        base_queryset.aggregate(
            todays_logs=Count("id", filter=Q(action_datetime__gte=_start_of_day(today))),
            this_week_logs=Count("id", filter=Q(action_datetime__gte=_start_of_day(week_start))),
            this_month_logs=Count("id", filter=Q(action_datetime__gte=_start_of_day(month_start))),
        )
    )

    trend_rows = _build_daily_trend(base_queryset, filters)

    top_users = list(
        filtered_queryset.annotate(actor_name=Coalesce("user__username", "username_snapshot", Value("Unknown")))
        .values("actor_name")
        .annotate(
            total_actions=Count("id"),
            login_count=Count("id", filter=Q(action_type=UserLogs.ActionType.LOGIN)),
            failed_count=Count("id", filter=Q(is_success=False)),
            last_activity=Max("action_datetime"),
        )
        .order_by("-total_actions", "actor_name")[:8]
    )

    action_label_map = dict(UserLogs.ActionType.choices)
    top_actions = []
    for row in (
        filtered_queryset.values("action_type")
        .annotate(
            count=Count("id"),
            success_count=Count("id", filter=Q(is_success=True)),
            failure_count=Count("id", filter=Q(is_success=False)),
        )
        .order_by("-count", "action_type")[:8]
    ):
        action_key = row["action_type"] or ""
        top_actions.append(
            {
                **row,
                "action_label": action_label_map.get(action_key, action_key or "Unclassified"),
            }
        )

    top_ips = list(
        filtered_queryset.exclude(ip_address="")
        .values("ip_address")
        .annotate(
            location=Coalesce(Max("location"), Value("Unknown")),
            count=Count("id"),
            unique_users=Count("username_snapshot", distinct=True, filter=~Q(username_snapshot="")),
            last_seen=Max("action_datetime"),
        )
        .order_by("-count", "ip_address")[:8]
    )

    paginator = Paginator(filtered_queryset, page_size)
    page_obj = paginator.get_page(page_number or 1)

    return {
        "summary": summary,
        "trend_rows": trend_rows,
        "top_users": top_users,
        "top_actions": top_actions,
        "top_ips": top_ips,
        "page_obj": page_obj,
        "logs": page_obj.object_list,
        "is_paginated": page_obj.has_other_pages(),
        "pagination_query": _querystring_without_page(query_params),
    }
