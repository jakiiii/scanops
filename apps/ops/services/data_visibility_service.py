from __future__ import annotations

from django.db.models import Q, QuerySet

from apps.ops.services import permission_service


MODULE_OWNER_FIELDS: dict[str, tuple[str, ...]] = {
    "targets": ("owner", "created_by"),
    "scan_profiles": ("created_by",),
    "scan_requests": ("requested_by",),
    "executions": ("scan_request__requested_by",),
    "results": ("execution__scan_request__requested_by",),
    "history": ("scan_request__requested_by",),
    "reports": (
        "generated_by",
        "source_execution__scan_request__requested_by",
        "source_result__execution__scan_request__requested_by",
        "comparison_left_result__execution__scan_request__requested_by",
        "comparison_right_result__execution__scan_request__requested_by",
        "asset__owner",
        "asset__target__owner",
        "asset__target__created_by",
    ),
    "schedules": ("created_by",),
    "schedule_runs": ("schedule__created_by",),
    "notifications": ("recipient",),
    "assets": ("owner", "target__owner", "target__created_by"),
    "asset_changes": ("asset__owner", "asset__target__owner", "asset__target__created_by"),
}


def user_can_view_all_data(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    return (
        getattr(user, "is_superuser", False)
        or permission_service.get_user_role_slug(user) in {
            permission_service.SUPER_ADMIN,
            permission_service.SECURITY_ADMIN,
        }
    )


def user_is_owner_scoped(user) -> bool:
    return getattr(user, "is_authenticated", False) and not user_can_view_all_data(user)


def _build_owner_predicate(user, owner_fields: tuple[str, ...]) -> Q:
    predicate = Q()
    for field in owner_fields:
        predicate |= Q(**{field: user})
    return predicate


def filter_queryset_for_user(
    queryset: QuerySet,
    user,
    *,
    module_name: str | None = None,
    owner_fields: tuple[str, ...] | None = None,
) -> QuerySet:
    if not getattr(user, "is_authenticated", False):
        return queryset.none()

    if user_can_view_all_data(user):
        return queryset

    resolved_owner_fields: tuple[str, ...] = owner_fields or MODULE_OWNER_FIELDS.get(module_name or "", ())
    if not resolved_owner_fields:
        return queryset.none()
    return queryset.filter(_build_owner_predicate(user, resolved_owner_fields))


def get_user_visible_targets(user, queryset: QuerySet | None = None) -> QuerySet:
    from apps.targets.models import Target

    queryset = queryset if queryset is not None else Target.objects.all()
    return filter_queryset_for_user(queryset, user, module_name="targets")


def get_user_visible_scan_profiles(user, queryset: QuerySet | None = None) -> QuerySet:
    from apps.scans.models import ScanProfile

    queryset = queryset if queryset is not None else ScanProfile.objects.all()
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    if user_can_view_all_data(user):
        return queryset
    return queryset.filter(Q(is_system=True) | Q(created_by=user))


def get_user_visible_scan_requests(user, queryset: QuerySet | None = None) -> QuerySet:
    from apps.scans.models import ScanRequest

    queryset = queryset if queryset is not None else ScanRequest.objects.all()
    return filter_queryset_for_user(queryset, user, module_name="scan_requests")


def get_user_visible_executions(user, queryset: QuerySet | None = None) -> QuerySet:
    from apps.scans.models import ScanExecution

    queryset = queryset if queryset is not None else ScanExecution.objects.all()
    return filter_queryset_for_user(queryset, user, module_name="executions")


def get_user_visible_results(user, queryset: QuerySet | None = None) -> QuerySet:
    from apps.scans.models import ScanResult

    queryset = queryset if queryset is not None else ScanResult.objects.all()
    return filter_queryset_for_user(queryset, user, module_name="results")


def get_user_visible_reports(user, queryset: QuerySet | None = None) -> QuerySet:
    from apps.reports.models import GeneratedReport

    queryset = queryset if queryset is not None else GeneratedReport.objects.all()
    return filter_queryset_for_user(queryset, user, module_name="reports")


def get_user_visible_schedules(user, queryset: QuerySet | None = None) -> QuerySet:
    from apps.schedules.models import ScanSchedule

    queryset = queryset if queryset is not None else ScanSchedule.objects.all()
    if not getattr(user, "is_authenticated", False):
        return queryset.filter(is_public=True)
    if user_can_view_all_data(user):
        return queryset
    return queryset.filter(Q(created_by=user) | Q(is_public=True))


def get_user_manageable_schedules(user, queryset: QuerySet | None = None) -> QuerySet:
    from apps.schedules.models import ScanSchedule

    queryset = queryset if queryset is not None else ScanSchedule.objects.all()
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    if user_can_view_all_data(user):
        return queryset
    return queryset.filter(created_by=user)


def can_user_manage_schedule(user, schedule) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user_can_view_all_data(user):
        return True
    return getattr(schedule, "created_by_id", None) == getattr(user, "id", None)


def get_user_visible_schedule_run_logs(user, queryset: QuerySet | None = None) -> QuerySet:
    from apps.schedules.models import ScheduleRunLog

    queryset = queryset if queryset is not None else ScheduleRunLog.objects.all()
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    if user_can_view_all_data(user):
        return queryset
    return queryset.filter(schedule__created_by=user)


def get_user_visible_notifications(user, queryset: QuerySet | None = None) -> QuerySet:
    from apps.notifications.models import Notification

    queryset = queryset if queryset is not None else Notification.objects.all()
    return filter_queryset_for_user(queryset, user, module_name="notifications")


def get_user_visible_assets(user, queryset: QuerySet | None = None) -> QuerySet:
    from apps.assets.models import Asset

    queryset = queryset if queryset is not None else Asset.objects.all()
    return filter_queryset_for_user(queryset, user, module_name="assets")


def get_user_visible_asset_changes(user, queryset: QuerySet | None = None) -> QuerySet:
    from apps.assets.models import AssetChangeLog

    queryset = queryset if queryset is not None else AssetChangeLog.objects.all()
    return filter_queryset_for_user(queryset, user, module_name="asset_changes")
