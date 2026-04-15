from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.ops.models import AppSetting


@dataclass(frozen=True, slots=True)
class SettingDefinition:
    key: str
    label: str
    description: str
    value_type: str
    default: Any
    choices: tuple[tuple[str, str], ...] = ()


SETTINGS_SCHEMA: dict[str, tuple[SettingDefinition, ...]] = {
    AppSetting.Category.GENERAL: (
        SettingDefinition(
            key="app_brand_name",
            label="App Branding",
            description="Primary product label shown in the interface.",
            value_type="text",
            default="ScanOps",
        ),
        SettingDefinition(
            key="default_landing_page",
            label="Default Landing Page",
            description="Initial module displayed after login.",
            value_type="choice",
            default="dashboard",
            choices=(
                ("dashboard", "Dashboard"),
                ("targets", "Targets"),
                ("new_scan", "New Scan"),
                ("running", "Running"),
                ("results", "Results"),
                ("reports", "Reports"),
            ),
        ),
        SettingDefinition(
            key="time_zone",
            label="Time Zone",
            description="Default application time zone.",
            value_type="text",
            default="UTC",
        ),
        SettingDefinition(
            key="language",
            label="Language",
            description="Default interface language.",
            value_type="choice",
            default="en-us",
            choices=(("en-us", "English (US)"), ("en-gb", "English (UK)")),
        ),
        SettingDefinition(
            key="scan_retention_days",
            label="Retention Defaults (Scan Data)",
            description="Retention duration for scan run data.",
            value_type="int",
            default=90,
        ),
        SettingDefinition(
            key="audit_retention_days",
            label="Retention Defaults (Audit Data)",
            description="Retention duration for admin audit trails.",
            value_type="int",
            default=180,
        ),
        SettingDefinition(
            key="compact_sidebar",
            label="General UI Preferences (Compact Sidebar)",
            description="Default to compact left navigation layout.",
            value_type="bool",
            default=False,
        ),
        SettingDefinition(
            key="show_help_tips",
            label="General UI Preferences (Show Tips)",
            description="Show contextual tips throughout the UI.",
            value_type="bool",
            default=True,
        ),
    ),
    AppSetting.Category.SCAN_POLICY: (
        SettingDefinition(
            key="allowed_scan_types",
            label="Allowed Scan Types",
            description="Scan modes that operators can execute.",
            value_type="list",
            default=["host_discovery", "quick_tcp", "top_100", "top_1000", "service_detection", "safe_basic"],
        ),
        SettingDefinition(
            key="blocked_scan_types",
            label="Blocked Scan Types",
            description="Scan modes blocked regardless of role.",
            value_type="list",
            default=[],
        ),
        SettingDefinition(
            key="max_ports_per_scan",
            label="Max Ports Per Scan",
            description="Maximum number of ports permitted per scan request.",
            value_type="int",
            default=1024,
        ),
        SettingDefinition(
            key="scan_timeout_seconds",
            label="Scan Timeout",
            description="Maximum runtime for a single scan.",
            value_type="int",
            default=900,
        ),
        SettingDefinition(
            key="max_concurrency",
            label="Max Concurrency",
            description="Upper bound for concurrent scan jobs.",
            value_type="int",
            default=20,
        ),
        SettingDefinition(
            key="safe_default_options",
            label="Safe Default Options",
            description="Require defaults to stay within safe profile baseline.",
            value_type="bool",
            default=True,
        ),
        SettingDefinition(
            key="aggressive_requires_approval",
            label="Aggressive Options Require Approval",
            description="Require privileged approval for aggressive scan modes.",
            value_type="bool",
            default=True,
        ),
    ),
    AppSetting.Category.ALLOWED_TARGETS: (
        SettingDefinition(
            key="whitelist_ranges",
            label="Whitelist Ranges",
            description="CIDR ranges that are always permitted.",
            value_type="list",
            default=["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"],
        ),
        SettingDefinition(
            key="blocked_ranges",
            label="Blocked Ranges",
            description="CIDR ranges that are denied by policy.",
            value_type="list",
            default=[],
        ),
        SettingDefinition(
            key="restrict_public_targets",
            label="Public Target Restriction",
            description="Disallow public internet targets by default.",
            value_type="bool",
            default=True,
        ),
        SettingDefinition(
            key="strict_target_validation",
            label="Validation Rules",
            description="Enforce strict target normalization and policy checks.",
            value_type="bool",
            default=True,
        ),
        SettingDefinition(
            key="approval_required_new_targets",
            label="Approval Required",
            description="Require approval workflow for newly submitted targets.",
            value_type="bool",
            default=True,
        ),
    ),
    AppSetting.Category.NOTIFICATIONS: (
        SettingDefinition(
            key="in_app_enabled",
            label="In-App Notifications",
            description="Enable in-app notification delivery.",
            value_type="bool",
            default=True,
        ),
        SettingDefinition(
            key="email_enabled",
            label="Email Notifications",
            description="Enable email notification delivery.",
            value_type="bool",
            default=False,
        ),
        SettingDefinition(
            key="severity_preferences",
            label="Severity Preferences",
            description="Minimum severities to deliver.",
            value_type="list",
            default=["warning", "error"],
        ),
        SettingDefinition(
            key="daily_digest_enabled",
            label="Digest Settings",
            description="Send scheduled digest notifications.",
            value_type="bool",
            default=True,
        ),
        SettingDefinition(
            key="digest_hour_utc",
            label="Digest Hour (UTC)",
            description="UTC hour for digest generation.",
            value_type="int",
            default=7,
        ),
    ),
    AppSetting.Category.EXPORTS: (
        SettingDefinition(
            key="default_report_format",
            label="Default Report Format",
            description="Preferred default report export format.",
            value_type="choice",
            default="html",
            choices=(("html", "HTML"), ("pdf", "PDF"), ("json", "JSON"), ("txt", "TXT")),
        ),
        SettingDefinition(
            key="branded_template",
            label="Branded Report Template",
            description="Default branding profile for report exports.",
            value_type="text",
            default="enterprise_standard",
        ),
        SettingDefinition(
            key="pdf_header_text",
            label="PDF Header",
            description="Header text rendered in PDF exports.",
            value_type="text",
            default="ScanOps Internal Use",
        ),
        SettingDefinition(
            key="pdf_footer_text",
            label="PDF Footer",
            description="Footer text rendered in PDF exports.",
            value_type="text",
            default="Authorized Internal Security Operations",
        ),
        SettingDefinition(
            key="export_retention_days",
            label="Export Retention",
            description="Retention duration for generated export files.",
            value_type="int",
            default=30,
        ),
        SettingDefinition(
            key="file_naming_pattern",
            label="File Naming Defaults",
            description="Pattern for generated export file names.",
            value_type="text",
            default="{type}-{target}-{date}",
        ),
    ),
    AppSetting.Category.UI: (
        SettingDefinition(
            key="default_theme",
            label="Dark/Light Mode Default",
            description="Theme preference for new sessions.",
            value_type="choice",
            default="dark",
            choices=(("dark", "Dark"), ("light", "Light"), ("system", "System")),
        ),
        SettingDefinition(
            key="compact_mode",
            label="Compact Mode",
            description="Use compact spacing across major views.",
            value_type="bool",
            default=False,
        ),
        SettingDefinition(
            key="data_density",
            label="Data Density",
            description="Preferred density for list-heavy layouts.",
            value_type="choice",
            default="comfortable",
            choices=(("comfortable", "Comfortable"), ("compact", "Compact")),
        ),
        SettingDefinition(
            key="table_page_size",
            label="Table Preferences",
            description="Default row count for paginated tables.",
            value_type="int",
            default=20,
        ),
        SettingDefinition(
            key="dashboard_card_style",
            label="Dashboard Card Style",
            description="Visual style for dashboard card components.",
            value_type="choice",
            default="standard",
            choices=(("standard", "Standard"), ("dense", "Dense"), ("minimal", "Minimal")),
        ),
    ),
}


def category_exists(category: str) -> bool:
    return category in SETTINGS_SCHEMA


def get_category_definitions(category: str) -> tuple[SettingDefinition, ...]:
    return SETTINGS_SCHEMA.get(category, ())


def _parse_setting_value(setting: AppSetting, definition: SettingDefinition):
    if definition.value_type == "bool":
        return setting.value_text.lower() in {"1", "true", "yes", "on"}
    if definition.value_type == "int":
        try:
            return int(setting.value_text)
        except (TypeError, ValueError):
            return int(definition.default)
    if definition.value_type == "list":
        raw = setting.value_json
        if isinstance(raw, list):
            return raw
        if isinstance(raw, str) and raw.strip():
            return [item.strip() for item in raw.split(",") if item.strip()]
        if setting.value_text.strip():
            return [item.strip() for item in setting.value_text.split(",") if item.strip()]
        return list(definition.default)
    if definition.value_type in {"choice", "text"}:
        return setting.value_text if setting.value_text != "" else definition.default
    return setting.value_json or definition.default


def get_category_values(category: str) -> dict[str, Any]:
    definitions = get_category_definitions(category)
    rows = {
        row.key: row
        for row in AppSetting.objects.filter(category=category, is_active=True)
    }
    values: dict[str, Any] = {}
    for definition in definitions:
        row = rows.get(definition.key)
        if row is None:
            values[definition.key] = definition.default
        else:
            values[definition.key] = _parse_setting_value(row, definition)
    return values


def _serialize_setting_value(definition: SettingDefinition, value: Any) -> tuple[str, Any]:
    if definition.value_type == "bool":
        return ("true" if bool(value) else "false", {"value": bool(value)})
    if definition.value_type == "int":
        value_int = int(value)
        return (str(value_int), {"value": value_int})
    if definition.value_type == "list":
        value_list = [str(item).strip() for item in (value or []) if str(item).strip()]
        return (",".join(value_list), value_list)
    if definition.value_type in {"choice", "text"}:
        value_text = str(value or "").strip()
        return (value_text, {"value": value_text})
    return (str(value), value)


def update_category_values(category: str, payload: dict[str, Any], *, user=None):
    definitions = get_category_definitions(category)
    if not definitions:
        return

    for definition in definitions:
        value = payload.get(definition.key, definition.default)
        value_text, value_json = _serialize_setting_value(definition, value)
        AppSetting.objects.update_or_create(
            key=definition.key,
            defaults={
                "category": category,
                "label": definition.label,
                "description": definition.description,
                "value_text": value_text,
                "value_json": value_json,
                "is_active": True,
                "updated_by": user,
            },
        )


def reset_category_to_defaults(category: str, *, user=None):
    defaults_payload = {definition.key: definition.default for definition in get_category_definitions(category)}
    update_category_values(category, defaults_payload, user=user)


def get_setting_value(key: str, default: Any = None):
    definition = None
    for _, definitions in SETTINGS_SCHEMA.items():
        for item in definitions:
            if item.key == key:
                definition = item
                break
        if definition:
            break

    row = AppSetting.objects.filter(key=key, is_active=True).first()
    if row is None:
        if definition is not None:
            return definition.default
        return default

    if definition is None:
        return row.value_json if row.value_json else row.value_text
    return _parse_setting_value(row, definition)
