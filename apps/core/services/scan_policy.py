from __future__ import annotations

from dataclasses import dataclass, field


ALLOWED_SCAN_TYPES = {
    "host_discovery",
    "quick_tcp",
    "top_100",
    "top_1000",
    "service_detection",
    "safe_basic",
}
ALLOWED_TIMING_PROFILES = {"normal", "balanced", "fast"}
MAX_PORT = 65535


@dataclass(slots=True)
class ScanPolicyResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    normalized_port_input: str = ""


def _parse_port_input(port_input: str) -> tuple[str, list[str]]:
    value = (port_input or "").strip()
    if not value:
        return "", []

    errors: list[str] = []
    normalized_parts: list[str] = []
    for raw_part in value.split(","):
        part = raw_part.strip()
        if not part:
            continue
        if "-" in part:
            bounds = [x.strip() for x in part.split("-", maxsplit=1)]
            if len(bounds) != 2 or not bounds[0].isdigit() or not bounds[1].isdigit():
                errors.append(f"Invalid port range '{part}'.")
                continue
            start, end = int(bounds[0]), int(bounds[1])
            if start < 1 or end > MAX_PORT or start > end:
                errors.append(f"Port range '{part}' is out of bounds.")
                continue
            normalized_parts.append(f"{start}-{end}")
        else:
            if not part.isdigit():
                errors.append(f"Invalid port '{part}'.")
                continue
            port = int(part)
            if port < 1 or port > MAX_PORT:
                errors.append(f"Port '{part}' is out of bounds.")
                continue
            normalized_parts.append(str(port))
    return ",".join(normalized_parts), errors


def validate_scan_options(payload: dict) -> ScanPolicyResult:
    scan_type = (payload.get("scan_type") or "").strip()
    timing_profile = (payload.get("timing_profile") or "").strip()
    port_input = payload.get("port_input") or ""

    enable_host_discovery = bool(payload.get("enable_host_discovery"))
    enable_service_detection = bool(payload.get("enable_service_detection"))
    enable_version_detection = bool(payload.get("enable_version_detection"))
    enable_os_detection = bool(payload.get("enable_os_detection"))
    enable_traceroute = bool(payload.get("enable_traceroute"))

    errors: list[str] = []
    warnings: list[str] = []

    if scan_type not in ALLOWED_SCAN_TYPES:
        errors.append("Unsupported scan type.")

    if timing_profile not in ALLOWED_TIMING_PROFILES:
        errors.append("Unsupported timing profile.")

    normalized_port_input, port_errors = _parse_port_input(port_input)
    errors.extend(port_errors)

    if enable_version_detection and not enable_service_detection:
        errors.append("Version detection requires service detection to be enabled.")

    if enable_os_detection and not enable_host_discovery:
        warnings.append("OS detection works best with host discovery enabled.")

    if scan_type == "host_discovery" and normalized_port_input:
        warnings.append("Port input is ignored for host discovery scans.")
        normalized_port_input = ""

    if scan_type == "safe_basic" and enable_traceroute:
        warnings.append("Traceroute may increase scan visibility on monitored networks.")

    return ScanPolicyResult(
        is_valid=not errors,
        errors=errors,
        warnings=warnings,
        normalized_port_input=normalized_port_input,
    )


def build_scan_summary(payload: dict, policy_result: ScanPolicyResult) -> dict:
    return {
        "target_label": getattr(payload.get("target"), "target_value", "") or "",
        "scan_type": payload.get("scan_type") or "",
        "timing_profile": payload.get("timing_profile") or "",
        "port_input": policy_result.normalized_port_input or "default",
        "host_discovery": bool(payload.get("enable_host_discovery")),
        "service_detection": bool(payload.get("enable_service_detection")),
        "version_detection": bool(payload.get("enable_version_detection")),
        "os_detection": bool(payload.get("enable_os_detection")),
        "traceroute": bool(payload.get("enable_traceroute")),
        "dns_resolution": bool(payload.get("enable_dns_resolution")),
        "errors": policy_result.errors,
        "warnings": policy_result.warnings,
    }
