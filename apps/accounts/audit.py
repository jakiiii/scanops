import logging
from functools import lru_cache
import ipaddress
from pathlib import Path

from django.conf import settings
from ipware import get_client_ip
from user_agents import parse

from apps.accounts.models import UserLogs


logger = logging.getLogger("exceptions_log")
UNKNOWN_LOCATION = "Unknown"


def _trim(value, length):
    if value is None:
        return ""
    value = str(value)
    return value[:length]


def _normalize_public_ip(ip_address: str) -> str:
    if not ip_address:
        return ""
    try:
        parsed = ipaddress.ip_address(ip_address)
    except ValueError:
        return ""
    if (
        parsed.is_private
        or parsed.is_loopback
        or parsed.is_multicast
        or parsed.is_reserved
        or parsed.is_link_local
        or parsed.is_unspecified
    ):
        return ""
    return str(parsed)


def _geoip_candidate_paths() -> list[Path]:
    configured_path = (getattr(settings, "GEOIP_PATH", "") or "").strip()
    candidates: list[Path] = []
    if configured_path:
        configured = Path(configured_path)
        if configured.is_file():
            candidates.append(configured)
        else:
            candidates.extend(
                [
                    configured / "GeoLite2-City.mmdb",
                    configured / "GeoLite2City.mmdb",
                ]
            )

    base_dir = Path(getattr(settings, "BASE_DIR", Path(__file__).resolve().parents[2]))
    candidates.extend(
        [
            base_dir / "GeoLite2City" / "GeoLite2City.mmdb",
            base_dir / "GeoLite2City" / "GeoLite2-City.mmdb",
        ]
    )

    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        candidate_str = str(candidate)
        if candidate_str in seen:
            continue
        seen.add(candidate_str)
        deduped.append(candidate)
    return deduped


@lru_cache(maxsize=1)
def _get_geoip_reader():
    try:
        from geoip2.database import Reader
    except Exception:
        return None

    for mmdb_path in _geoip_candidate_paths():
        if not mmdb_path.exists():
            continue
        try:
            return Reader(str(mmdb_path))
        except Exception:
            logger.exception("Failed to initialize GeoIP reader from %s", mmdb_path)
    return None


def resolve_location_from_ip(ip_address: str) -> str:
    normalized_ip = _normalize_public_ip(ip_address)
    if not normalized_ip:
        return UNKNOWN_LOCATION

    reader = _get_geoip_reader()
    if reader is None:
        return UNKNOWN_LOCATION

    try:
        city_response = reader.city(normalized_ip)
    except Exception:
        return UNKNOWN_LOCATION

    city = _trim(getattr(city_response.city, "name", ""), 80)
    country = _trim(getattr(city_response.country, "name", ""), 80)
    if city and country and city.lower() != country.lower():
        return _trim(f"{city}, {country}", 160)
    if country:
        return _trim(country, 160)
    if city:
        return _trim(city, 160)
    return UNKNOWN_LOCATION


def extract_request_audit_context(request):
    if request is None:
        return {
            "ip_address": "",
            "location": UNKNOWN_LOCATION,
            "request_method": "",
            "path": "",
            "user_agent": "",
            "browser": "",
            "device": "",
            "operating_system": "",
        }

    ip_address, _ = get_client_ip(request)
    ip_address = ip_address or request.META.get("REMOTE_ADDR", "")
    user_agent_string = request.META.get("HTTP_USER_AGENT", "")

    browser = ""
    device = ""
    operating_system = ""
    if user_agent_string:
        try:
            user_agent = parse(user_agent_string)
            browser = _trim(
                " ".join(part for part in [user_agent.browser.family, user_agent.browser.version_string] if part),
                255,
            )
            operating_system = _trim(
                " ".join(part for part in [user_agent.os.family, user_agent.os.version_string] if part),
                255,
            )
            device = _trim(user_agent.device.family, 255)
        except Exception:
            logger.exception("Failed to parse user agent for audit log")

    return {
        "ip_address": _trim(ip_address, 45),
        "location": _trim(resolve_location_from_ip(ip_address), 160) or UNKNOWN_LOCATION,
        "request_method": _trim(getattr(request, "method", ""), 10),
        "path": _trim(request.get_full_path(), 500),
        "user_agent": user_agent_string,
        "browser": browser,
        "device": device,
        "operating_system": operating_system,
    }


def create_user_log(
    *,
    action_type,
    description,
    request=None,
    user=None,
    username_snapshot="",
    is_success=True,
    target=None,
):
    username = username_snapshot or getattr(user, "username", "")
    target_model = ""
    target_object_id = ""
    object_repr = ""

    if target is not None:
        target_model = _trim(target._meta.label, 120)
        target_object_id = _trim(getattr(target, "pk", ""), 64)
        object_repr = _trim(target, 255)

    try:
        return UserLogs.objects.create(
            user=user if getattr(user, "pk", None) else None,
            username_snapshot=_trim(username, 150),
            action_type=action_type,
            description=_trim(description, 500),
            is_success=is_success,
            target_model=target_model,
            target_object_id=target_object_id,
            object_repr=object_repr,
            **extract_request_audit_context(request),
        )
    except Exception:
        logger.exception(
            "Failed to create user audit log",
            extra={
                "action_type": action_type,
                "username_snapshot": username,
                "user_id": getattr(user, "pk", None),
            },
        )
        return None


class AuditLogAdminMixin:
    audit_log_create_type = UserLogs.ActionType.ADMIN_CREATE
    audit_log_update_type = UserLogs.ActionType.ADMIN_UPDATE
    audit_log_delete_type = UserLogs.ActionType.ADMIN_DELETE

    def _build_audit_description(self, verb, obj):
        return f"{verb} {obj._meta.verbose_name}: {obj}"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        verb = "Updated" if change else "Created"
        action_type = self.audit_log_update_type if change else self.audit_log_create_type
        create_user_log(
            action_type=action_type,
            description=self._build_audit_description(verb, obj),
            request=request,
            user=request.user,
            target=obj,
        )

    def delete_model(self, request, obj):
        target = _DeletedObjectStub(obj._meta.label, obj._meta.verbose_name, obj.pk, str(obj))
        super().delete_model(request, obj)
        create_user_log(
            action_type=self.audit_log_delete_type,
            description=self._build_audit_description("Deleted", target),
            request=request,
            user=request.user,
            target=target,
        )

    def delete_queryset(self, request, queryset):
        targets = [
            _DeletedObjectStub(obj._meta.label, obj._meta.verbose_name, obj.pk, str(obj))
            for obj in queryset
        ]
        super().delete_queryset(request, queryset)
        for target in targets:
            create_user_log(
                action_type=self.audit_log_delete_type,
                description=self._build_audit_description("Deleted", target),
                request=request,
                user=request.user,
                target=target,
            )


class _DeletedObjectStub:
    def __init__(self, label, verbose_name, pk, representation):
        self._meta = type("Meta", (), {"label": label, "verbose_name": verbose_name})
        self.pk = pk
        self._representation = representation

    def __str__(self):
        return self._representation
