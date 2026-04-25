from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from ipaddress import ip_address

from django.db import transaction
from django.utils import timezone

from apps.assets.models import Asset, AssetChangeLog, AssetSnapshot
from apps.notifications.services.notification_service import notify_asset_changed
from apps.ops.services import data_visibility_service
from apps.scans.models import ScanPortResult, ScanResult


def _risk_from_result(result: ScanResult) -> tuple[Decimal, str]:
    high = result.port_results.filter(risk_level=ScanPortResult.RiskLevel.HIGH).count()
    medium = result.port_results.filter(risk_level=ScanPortResult.RiskLevel.MEDIUM).count()
    low = result.port_results.filter(risk_level=ScanPortResult.RiskLevel.LOW).count()
    info = result.port_results.filter(risk_level=ScanPortResult.RiskLevel.INFO).count()
    score = min(100, (high * 20) + (medium * 10) + (low * 4) + info)
    if score >= 80:
        level = Asset.RiskLevel.CRITICAL
    elif score >= 55:
        level = Asset.RiskLevel.HIGH
    elif score >= 30:
        level = Asset.RiskLevel.MEDIUM
    elif score > 0:
        level = Asset.RiskLevel.LOW
    else:
        level = Asset.RiskLevel.INFO
    return Decimal(f"{score:.2f}"), level


def _safe_ip(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(ip_address(value))
    except ValueError:
        return None


def _ports_payload(result: ScanResult) -> list[dict]:
    return [
        {
            "port": row.port,
            "protocol": row.protocol,
            "state": row.state,
            "service_name": row.service_name,
            "service_version": row.service_version,
            "risk_level": row.risk_level,
        }
        for row in result.port_results.all().order_by("port", "protocol")
    ]


def _services_payload(open_ports: list[dict]) -> list[dict]:
    grouped = defaultdict(set)
    versions = {}
    for item in open_ports:
        service = item.get("service_name") or "unknown"
        grouped[service].add(item.get("port"))
        version = item.get("service_version") or ""
        if version:
            versions[service] = version
    payload = []
    for service, ports in sorted(grouped.items()):
        payload.append(
            {
                "service_name": service,
                "ports": sorted(ports),
                "service_version": versions.get(service, ""),
            }
        )
    return payload


def _compare_snapshots(previous: AssetSnapshot | None, current: AssetSnapshot) -> dict:
    if previous is None:
        return {
            "ports_added": current.open_ports_json,
            "ports_removed": [],
            "service_changed": [],
            "os_changed": False,
        }

    prev_ports = {(item.get("port"), item.get("protocol")): item for item in previous.open_ports_json}
    curr_ports = {(item.get("port"), item.get("protocol")): item for item in current.open_ports_json}
    added_keys = sorted(set(curr_ports.keys()) - set(prev_ports.keys()))
    removed_keys = sorted(set(prev_ports.keys()) - set(curr_ports.keys()))
    common_keys = sorted(set(prev_ports.keys()) & set(curr_ports.keys()))

    service_changed = []
    for key in common_keys:
        before = prev_ports[key]
        after = curr_ports[key]
        if (
            before.get("service_name") != after.get("service_name")
            or before.get("service_version") != after.get("service_version")
            or before.get("state") != after.get("state")
        ):
            service_changed.append(
                {
                    "port": key[0],
                    "protocol": key[1],
                    "before": before,
                    "after": after,
                }
            )

    return {
        "ports_added": [curr_ports[key] for key in added_keys],
        "ports_removed": [prev_ports[key] for key in removed_keys],
        "service_changed": service_changed,
        "os_changed": previous.operating_system != current.operating_system,
    }


@transaction.atomic
def sync_asset_from_result(result: ScanResult, *, notify: bool = True) -> Asset:
    target = result.execution.scan_request.target
    derived_owner = result.execution.scan_request.requested_by or target.owner or target.created_by
    identifier = target.target_value or result.target_snapshot
    asset_name = target.name or target.target_value or result.target_snapshot
    asset_ip = None
    if target.target_type in {"ip", "ipv6"}:
        asset_ip = _safe_ip(target.target_value)
    if not asset_ip:
        asset_ip = _safe_ip(result.target_snapshot)

    risk_score, risk_level = _risk_from_result(result)
    status = Asset.Status.MONITORING
    if result.host_status == ScanResult.HostStatus.UP:
        status = Asset.Status.ACTIVE
    elif result.host_status == ScanResult.HostStatus.DOWN:
        status = Asset.Status.INACTIVE

    asset, created = Asset.objects.get_or_create(
        canonical_identifier=identifier,
        defaults={
            "name": asset_name,
            "target": target,
            "hostname": target.name or "",
            "ip_address": asset_ip,
            "operating_system": result.os_guess,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "owner": derived_owner,
            "owner_name": (derived_owner.username if derived_owner else ""),
            "notes": "",
            "last_seen_at": result.generated_at,
            "last_scanned_at": result.generated_at,
            "status": status,
            "current_open_ports_count": result.total_open_ports,
        },
    )
    if not created:
        asset.name = asset_name
        asset.target = target
        asset.hostname = target.name or asset.hostname or result.target_snapshot
        if asset_ip:
            asset.ip_address = asset_ip
        asset.operating_system = result.os_guess
        asset.risk_score = risk_score
        asset.risk_level = risk_level
        if derived_owner and asset.owner_id != derived_owner.id:
            asset.owner = derived_owner
        if derived_owner:
            asset.owner_name = derived_owner.username
        asset.last_seen_at = result.generated_at
        asset.last_scanned_at = result.generated_at
        asset.status = status
        asset.current_open_ports_count = result.total_open_ports
        asset.save()

    open_ports_payload = _ports_payload(result)
    services_payload = _services_payload(open_ports_payload)

    snapshot = AssetSnapshot.objects.create(
        asset=asset,
        source_result=result,
        hostname=asset.hostname,
        ip_address=asset.ip_address,
        operating_system=asset.operating_system,
        open_ports_json=open_ports_payload,
        services_json=services_payload,
        raw_summary_json={
            "open_ports": result.total_open_ports,
            "closed_ports": result.total_closed_ports,
            "filtered_ports": result.total_filtered_ports,
            "services": result.total_services_detected,
            "os_guess": result.os_guess,
            "risk_level": risk_level,
            "risk_score": float(risk_score),
        },
    )

    previous_snapshot = asset.snapshots.exclude(pk=snapshot.pk).order_by("-created_at").first()
    diff = _compare_snapshots(previous_snapshot, snapshot)
    change_summaries = []

    if created:
        change_summaries.append("Asset was created from scan result.")
        AssetChangeLog.objects.create(
            asset=asset,
            previous_snapshot=None,
            current_snapshot=snapshot,
            change_type=AssetChangeLog.ChangeType.ASSET_CREATED,
            summary="Asset created from first available scan snapshot.",
            diff_json={"initial_ports": open_ports_payload},
        )
    else:
        if diff["ports_added"]:
            summary = f"{len(diff['ports_added'])} new open ports detected."
            change_summaries.append(summary)
            AssetChangeLog.objects.create(
                asset=asset,
                previous_snapshot=previous_snapshot,
                current_snapshot=snapshot,
                change_type=AssetChangeLog.ChangeType.PORTS_ADDED,
                summary=summary,
                diff_json={"ports_added": diff["ports_added"]},
            )
        if diff["ports_removed"]:
            summary = f"{len(diff['ports_removed'])} previously open ports are now removed/closed."
            change_summaries.append(summary)
            AssetChangeLog.objects.create(
                asset=asset,
                previous_snapshot=previous_snapshot,
                current_snapshot=snapshot,
                change_type=AssetChangeLog.ChangeType.PORTS_REMOVED,
                summary=summary,
                diff_json={"ports_removed": diff["ports_removed"]},
            )
        if diff["service_changed"]:
            summary = f"{len(diff['service_changed'])} service fingerprints changed."
            change_summaries.append(summary)
            AssetChangeLog.objects.create(
                asset=asset,
                previous_snapshot=previous_snapshot,
                current_snapshot=snapshot,
                change_type=AssetChangeLog.ChangeType.SERVICE_CHANGED,
                summary=summary,
                diff_json={"service_changed": diff["service_changed"]},
            )
        if diff["os_changed"]:
            summary = f"Operating system changed: {previous_snapshot.operating_system} -> {snapshot.operating_system}"
            change_summaries.append(summary)
            AssetChangeLog.objects.create(
                asset=asset,
                previous_snapshot=previous_snapshot,
                current_snapshot=snapshot,
                change_type=AssetChangeLog.ChangeType.OS_CHANGED,
                summary=summary,
                diff_json={
                    "from": previous_snapshot.operating_system,
                    "to": snapshot.operating_system,
                },
            )
        if not change_summaries:
            summary = "Asset snapshot updated; no material changes detected."
            change_summaries.append(summary)
            AssetChangeLog.objects.create(
                asset=asset,
                previous_snapshot=previous_snapshot,
                current_snapshot=snapshot,
                change_type=AssetChangeLog.ChangeType.ASSET_UPDATED,
                summary=summary,
                diff_json={},
            )

    if notify:
        recipient = result.execution.scan_request.requested_by
        if recipient and change_summaries:
            notify_asset_changed(asset=asset, summary=change_summaries[0], recipient=recipient)
    return asset


def sync_assets_from_results(*, limit: int = 100, user=None) -> int:
    queryset = (
        ScanResult.objects.select_related("execution__scan_request__target", "execution__scan_request__requested_by")
        .prefetch_related("port_results")
        .order_by("-generated_at")
    )
    if user is not None:
        queryset = data_visibility_service.get_user_visible_results(user, queryset=queryset)
    queryset = queryset[:limit]
    count = 0
    for result in queryset:
        sync_asset_from_result(result, notify=False)
        count += 1
    return count


def build_asset_detail_context(asset: Asset, *, user=None) -> dict:
    latest_snapshot = asset.snapshots.order_by("-created_at").first()
    snapshots = asset.snapshots.order_by("-created_at")[:20]
    change_logs = asset.change_logs.select_related("previous_snapshot", "current_snapshot").order_by("-created_at")[:40]

    if asset.target_id:
        related_results = (
            ScanResult.objects.select_related("execution__scan_request__profile")
            .filter(execution__scan_request__target=asset.target)
            .order_by("-generated_at")
        )
        if user is not None:
            related_results = data_visibility_service.get_user_visible_results(user, queryset=related_results)
        related_results = related_results[:15]
    else:
        related_results = ScanResult.objects.none()

    current_ports = latest_snapshot.open_ports_json if latest_snapshot else []
    service_inventory = latest_snapshot.services_json if latest_snapshot else []

    summary = {
        "snapshots": asset.snapshots.count(),
        "changes": asset.change_logs.count(),
        "critical_changes": asset.change_logs.filter(
            change_type__in=[
                AssetChangeLog.ChangeType.PORTS_ADDED,
                AssetChangeLog.ChangeType.OS_CHANGED,
            ]
        ).count(),
    }
    return {
        "latest_snapshot": latest_snapshot,
        "snapshots": snapshots,
        "change_logs": change_logs,
        "related_results": related_results,
        "current_ports": current_ports,
        "service_inventory": service_inventory,
        "summary": summary,
    }


def global_asset_changes(*, limit: int | None = None):
    queryset = AssetChangeLog.objects.select_related("asset", "previous_snapshot", "current_snapshot").order_by("-created_at")
    if limit is not None:
        return queryset[:limit]
    return queryset
