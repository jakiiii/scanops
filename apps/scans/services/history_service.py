from __future__ import annotations

from django.db.models import Q, QuerySet

from apps.scans.models import ScanExecution, ScanRequest
from apps.scans.services.execution_service import create_execution_from_request


def apply_execution_filters(
    queryset: QuerySet[ScanExecution],
    *,
    q: str = "",
    status: str = "",
    target=None,
    profile=None,
    requested_by=None,
    date_from=None,
    date_to=None,
) -> QuerySet[ScanExecution]:
    q = (q or "").strip()
    if q:
        queryset = queryset.filter(
            Q(execution_id__icontains=q)
            | Q(scan_request__target__target_value__icontains=q)
            | Q(scan_request__target__name__icontains=q)
            | Q(worker_name__icontains=q)
        )
    if status:
        queryset = queryset.filter(status=status)
    if target:
        queryset = queryset.filter(scan_request__target=target)
    if profile:
        queryset = queryset.filter(scan_request__profile=profile)
    if requested_by:
        queryset = queryset.filter(scan_request__requested_by=requested_by)
    if date_from:
        queryset = queryset.filter(created_at__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(created_at__date__lte=date_to)
    return queryset


def clone_scan_request_from_execution(execution: ScanExecution, *, user) -> ScanRequest:
    request = execution.scan_request
    cloned_request = ScanRequest.objects.create(
        target=request.target,
        profile=request.profile,
        scan_type=request.scan_type,
        port_input=request.port_input,
        enable_host_discovery=request.enable_host_discovery,
        enable_service_detection=request.enable_service_detection,
        enable_version_detection=request.enable_version_detection,
        enable_os_detection=request.enable_os_detection,
        enable_traceroute=request.enable_traceroute,
        enable_dns_resolution=request.enable_dns_resolution,
        timing_profile=request.timing_profile,
        status=ScanRequest.Status.PENDING,
        validation_summary=request.validation_summary,
        notes=(request.notes or "") + "\n[Cloned from execution %s]" % execution.execution_id,
        requested_by=user,
    )
    return cloned_request


def rerun_execution(execution: ScanExecution, *, user) -> ScanExecution:
    cloned_request = clone_scan_request_from_execution(execution, user=user)
    return create_execution_from_request(cloned_request, status_message=f"Re-run from {execution.execution_id}.")


def permanently_delete_execution(execution: ScanExecution) -> None:
    execution.delete()
