from __future__ import annotations

from typing import Any

from django.template.loader import render_to_string
from django.utils import timezone

from apps.assets.models import Asset
from apps.reports.models import GeneratedReport
from apps.scans.models import ScanExecution, ScanPortResult, ScanResult
from apps.scans.services.comparison_service import compare_results


def _result_payload(result: ScanResult | None) -> dict[str, Any]:
    if result is None:
        return {}
    high_risk_count = result.port_results.filter(risk_level=ScanPortResult.RiskLevel.HIGH).count()
    medium_risk_count = result.port_results.filter(risk_level=ScanPortResult.RiskLevel.MEDIUM).count()
    return {
        "id": result.pk,
        "execution_id": result.execution.execution_id,
        "target": result.target_snapshot,
        "host_status": result.host_status,
        "open_ports": result.total_open_ports,
        "closed_ports": result.total_closed_ports,
        "filtered_ports": result.total_filtered_ports,
        "services": result.total_services_detected,
        "os_guess": result.os_guess,
        "duration_seconds": result.execution.duration_seconds,
        "generated_at": result.generated_at.isoformat(),
        "high_risk_count": high_risk_count,
        "medium_risk_count": medium_risk_count,
        "ports": [
            {
                "port": row.port,
                "protocol": row.protocol,
                "state": row.state,
                "service_name": row.service_name,
                "service_version": row.service_version,
                "risk_level": row.risk_level,
            }
            for row in result.port_results.all().order_by("port", "protocol")
        ],
    }


def _execution_payload(execution: ScanExecution | None) -> dict[str, Any]:
    if execution is None:
        return {}
    return {
        "id": execution.pk,
        "execution_id": execution.execution_id,
        "status": execution.status,
        "queue_status": execution.queue_status,
        "target": execution.scan_request.target.target_value,
        "profile": (
            execution.scan_request.profile.name
            if execution.scan_request.profile
            else execution.scan_request.get_scan_type_display()
        ),
        "requested_by": (
            execution.scan_request.requested_by.username
            if execution.scan_request.requested_by
            else "System"
        ),
        "started_at": execution.started_at.isoformat() if execution.started_at else None,
        "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
        "duration_seconds": execution.duration_seconds,
        "progress_percent": execution.progress_percent,
    }


def _asset_payload(asset: Asset | None) -> dict[str, Any]:
    if asset is None:
        return {}
    latest_snapshot = asset.snapshots.order_by("-created_at").first()
    return {
        "id": asset.pk,
        "name": asset.name,
        "hostname": asset.hostname,
        "ip_address": asset.ip_address,
        "canonical_identifier": asset.canonical_identifier,
        "operating_system": asset.operating_system,
        "risk_score": float(asset.risk_score),
        "risk_level": asset.risk_level,
        "owner_name": asset.owner_name,
        "status": asset.status,
        "current_open_ports_count": asset.current_open_ports_count,
        "last_seen_at": asset.last_seen_at.isoformat() if asset.last_seen_at else None,
        "last_scanned_at": asset.last_scanned_at.isoformat() if asset.last_scanned_at else None,
        "latest_snapshot_ports": (latest_snapshot.open_ports_json if latest_snapshot else []),
    }


def _comparison_payload(
    comparison_left_result: ScanResult | None,
    comparison_right_result: ScanResult | None,
) -> dict[str, Any]:
    if not comparison_left_result or not comparison_right_result:
        return {}

    raw = compare_results(comparison_left_result, comparison_right_result)
    return {
        "left_result": {
            "id": comparison_left_result.pk,
            "execution_id": comparison_left_result.execution.execution_id,
            "target": comparison_left_result.target_snapshot,
        },
        "right_result": {
            "id": comparison_right_result.pk,
            "execution_id": comparison_right_result.execution.execution_id,
            "target": comparison_right_result.target_snapshot,
        },
        "added_ports": raw.get("added_ports", []),
        "removed_ports": raw.get("removed_ports", []),
        "changed_ports": raw.get("changed_ports", []),
        "os_change": raw.get("os_change"),
        "host_status_change": raw.get("host_status_change"),
        "summary": raw.get("summary", {}),
    }


def build_report_payload(
    *,
    report_type: str,
    source_result: ScanResult | None = None,
    source_execution: ScanExecution | None = None,
    comparison_left_result: ScanResult | None = None,
    comparison_right_result: ScanResult | None = None,
    asset: Asset | None = None,
    include_sections: dict[str, bool] | None = None,
    summary_notes: str = "",
) -> dict[str, Any]:
    include_sections = include_sections or {}
    comparison_payload = _comparison_payload(comparison_left_result, comparison_right_result)

    return {
        "generated_at": timezone.now().isoformat(),
        "report_type": report_type,
        "sections": include_sections,
        "summary_notes": summary_notes,
        "result": _result_payload(source_result),
        "execution": _execution_payload(source_execution),
        "asset": _asset_payload(asset),
        "comparison": comparison_payload,
    }


def render_report_html(*, title: str, payload: dict[str, Any]) -> str:
    return render_to_string(
        "reports/generated_report_content.html",
        {
            "title": title,
            "payload": payload,
        },
    )


def _summary_line(payload: dict[str, Any]) -> str:
    result = payload.get("result") or {}
    comparison = payload.get("comparison") or {}
    asset = payload.get("asset") or {}

    if comparison:
        total_changes = comparison.get("summary", {}).get("total_changes", 0)
        return f"Comparison summary with {total_changes} detected changes."
    if result:
        return (
            f"Host {result.get('target', '-')}: "
            f"{result.get('open_ports', 0)} open ports, "
            f"{result.get('services', 0)} services detected."
        )
    if asset:
        return (
            f"Asset {asset.get('name', '-')}: "
            f"risk {asset.get('risk_level', 'info')} "
            f"({asset.get('risk_score', 0)})."
        )
    execution = payload.get("execution") or {}
    if execution:
        return f"Execution {execution.get('execution_id', '-')}: status {execution.get('status', '-')}"
    return "Generated report payload."


def generate_report_from_cleaned_data(cleaned_data: dict[str, Any], *, user) -> GeneratedReport:
    include_sections = {
        "summary": bool(cleaned_data.get("include_summary")),
        "ports": bool(cleaned_data.get("include_ports")),
        "services": bool(cleaned_data.get("include_services")),
        "findings": bool(cleaned_data.get("include_findings")),
        "timeline": bool(cleaned_data.get("include_timeline")),
    }

    payload = build_report_payload(
        report_type=cleaned_data["report_type"],
        source_result=cleaned_data.get("source_result"),
        source_execution=cleaned_data.get("source_execution"),
        comparison_left_result=cleaned_data.get("comparison_left_result"),
        comparison_right_result=cleaned_data.get("comparison_right_result"),
        asset=cleaned_data.get("asset"),
        include_sections=include_sections,
        summary_notes=cleaned_data.get("summary_notes", ""),
    )
    title = cleaned_data["title"]
    rendered_html = render_report_html(title=title, payload=payload)
    report = GeneratedReport.objects.create(
        title=title,
        report_type=cleaned_data["report_type"],
        source_result=cleaned_data.get("source_result"),
        source_execution=cleaned_data.get("source_execution"),
        comparison_left_result=cleaned_data.get("comparison_left_result"),
        comparison_right_result=cleaned_data.get("comparison_right_result"),
        asset=cleaned_data.get("asset"),
        generated_by=user,
        format=cleaned_data["format"],
        status=GeneratedReport.Status.GENERATED,
        summary=_summary_line(payload),
        report_payload_json=payload,
        rendered_html=rendered_html,
    )
    return report


def regenerate_report(report: GeneratedReport, *, user=None) -> GeneratedReport:
    payload = build_report_payload(
        report_type=report.report_type,
        source_result=report.source_result,
        source_execution=report.source_execution,
        comparison_left_result=report.comparison_left_result,
        comparison_right_result=report.comparison_right_result,
        asset=report.asset,
        include_sections=(report.report_payload_json or {}).get("sections", {}),
        summary_notes=(report.report_payload_json or {}).get("summary_notes", ""),
    )
    report.report_payload_json = payload
    report.summary = _summary_line(payload)
    report.rendered_html = render_report_html(title=report.title, payload=payload)
    report.status = GeneratedReport.Status.GENERATED
    if user is not None and report.generated_by_id is None:
        report.generated_by = user
    report.save(update_fields=["report_payload_json", "summary", "rendered_html", "status", "generated_by", "updated_at"])
    return report
