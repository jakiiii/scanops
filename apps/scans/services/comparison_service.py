from __future__ import annotations

from apps.scans.models import ScanResult
from apps.scans.services.result_service import get_previous_result


def _port_key(port_row) -> tuple[int, str]:
    return port_row.port, port_row.protocol


def compare_results(base_result: ScanResult, current_result: ScanResult) -> dict:
    base_ports = { _port_key(row): row for row in base_result.port_results.all() }
    current_ports = { _port_key(row): row for row in current_result.port_results.all() }

    added_keys = sorted(set(current_ports.keys()) - set(base_ports.keys()))
    removed_keys = sorted(set(base_ports.keys()) - set(current_ports.keys()))
    common_keys = sorted(set(base_ports.keys()) & set(current_ports.keys()))

    added_ports = [
        {
            "port": key[0],
            "protocol": key[1],
            "service": current_ports[key].service_name,
            "version": current_ports[key].service_version,
            "risk": current_ports[key].risk_level,
        }
        for key in added_keys
    ]
    removed_ports = [
        {
            "port": key[0],
            "protocol": key[1],
            "service": base_ports[key].service_name,
            "version": base_ports[key].service_version,
            "risk": base_ports[key].risk_level,
        }
        for key in removed_keys
    ]

    changed_ports = []
    for key in common_keys:
        before = base_ports[key]
        after = current_ports[key]
        diffs = {}
        if before.state != after.state:
            diffs["state"] = {"from": before.state, "to": after.state}
        if before.service_name != after.service_name:
            diffs["service_name"] = {"from": before.service_name, "to": after.service_name}
        if before.service_version != after.service_version:
            diffs["service_version"] = {"from": before.service_version, "to": after.service_version}
        if before.risk_level != after.risk_level:
            diffs["risk_level"] = {"from": before.risk_level, "to": after.risk_level}
        if diffs:
            changed_ports.append(
                {
                    "port": key[0],
                    "protocol": key[1],
                    "changes": diffs,
                }
            )

    os_changed = base_result.os_guess != current_result.os_guess
    host_status_changed = base_result.host_status != current_result.host_status

    return {
        "base_result": base_result,
        "current_result": current_result,
        "added_ports": added_ports,
        "removed_ports": removed_ports,
        "changed_ports": changed_ports,
        "os_change": {"from": base_result.os_guess, "to": current_result.os_guess} if os_changed else None,
        "host_status_change": {"from": base_result.host_status, "to": current_result.host_status} if host_status_changed else None,
        "summary": {
            "total_changes": len(added_ports) + len(removed_ports) + len(changed_ports) + int(os_changed) + int(host_status_changed),
            "added_count": len(added_ports),
            "removed_count": len(removed_ports),
            "changed_count": len(changed_ports),
            "os_changed": os_changed,
            "host_status_changed": host_status_changed,
        },
    }


def build_comparison_from_current(current_result: ScanResult, *, user=None) -> dict | None:
    previous = get_previous_result(current_result, user=user)
    if not previous:
        return None
    return compare_results(previous, current_result)
