from __future__ import annotations

from typing import Iterable

from apps.ops.models import PermissionRule, Role, UserProfile


PERMISSION_KEYS = [choice for choice, _ in PermissionRule.PermissionKey.choices]

DEFAULT_ROLE_MATRIX: dict[str, dict[str, bool]] = {
    "super_admin": {key: True for key in PERMISSION_KEYS},
    "security_admin": {
        PermissionRule.PermissionKey.MANAGE_USERS: True,
        PermissionRule.PermissionKey.MANAGE_SETTINGS: True,
        PermissionRule.PermissionKey.MANAGE_PROFILES: True,
        PermissionRule.PermissionKey.MANAGE_SCHEDULES: True,
        PermissionRule.PermissionKey.VIEW_SYSTEM_HEALTH: True,
        PermissionRule.PermissionKey.RUN_SCANS: True,
        PermissionRule.PermissionKey.ARCHIVE_RESULTS: True,
        PermissionRule.PermissionKey.GENERATE_REPORTS: True,
    },
    "analyst": {
        PermissionRule.PermissionKey.MANAGE_USERS: False,
        PermissionRule.PermissionKey.MANAGE_SETTINGS: False,
        PermissionRule.PermissionKey.MANAGE_PROFILES: False,
        PermissionRule.PermissionKey.MANAGE_SCHEDULES: True,
        PermissionRule.PermissionKey.VIEW_SYSTEM_HEALTH: True,
        PermissionRule.PermissionKey.RUN_SCANS: True,
        PermissionRule.PermissionKey.ARCHIVE_RESULTS: True,
        PermissionRule.PermissionKey.GENERATE_REPORTS: True,
    },
    "operator": {
        PermissionRule.PermissionKey.MANAGE_USERS: False,
        PermissionRule.PermissionKey.MANAGE_SETTINGS: False,
        PermissionRule.PermissionKey.MANAGE_PROFILES: False,
        PermissionRule.PermissionKey.MANAGE_SCHEDULES: False,
        PermissionRule.PermissionKey.VIEW_SYSTEM_HEALTH: True,
        PermissionRule.PermissionKey.RUN_SCANS: True,
        PermissionRule.PermissionKey.ARCHIVE_RESULTS: False,
        PermissionRule.PermissionKey.GENERATE_REPORTS: True,
    },
    "viewer": {
        PermissionRule.PermissionKey.MANAGE_USERS: False,
        PermissionRule.PermissionKey.MANAGE_SETTINGS: False,
        PermissionRule.PermissionKey.MANAGE_PROFILES: False,
        PermissionRule.PermissionKey.MANAGE_SCHEDULES: False,
        PermissionRule.PermissionKey.VIEW_SYSTEM_HEALTH: True,
        PermissionRule.PermissionKey.RUN_SCANS: False,
        PermissionRule.PermissionKey.ARCHIVE_RESULTS: False,
        PermissionRule.PermissionKey.GENERATE_REPORTS: False,
    },
}

DEFAULT_ROLES = (
    ("Super Admin", "super_admin", "Platform-level administrative authority.", True),
    ("Security Admin", "security_admin", "Security governance and policy administration.", True),
    ("Analyst", "analyst", "Investigation and analysis workflows.", True),
    ("Operator", "operator", "Operational scan execution role.", True),
    ("Viewer", "viewer", "Read-only role for approved observers.", True),
)


def bootstrap_default_roles() -> list[Role]:
    roles: list[Role] = []
    for name, slug, description, is_system in DEFAULT_ROLES:
        role, _ = Role.objects.get_or_create(
            slug=slug,
            defaults={"name": name, "description": description, "is_system": is_system},
        )
        if role.name != name or role.description != description:
            role.name = name
            role.description = description
            role.is_system = is_system
            role.save(update_fields=["name", "description", "is_system", "updated_at"])
        roles.append(role)
        seed_role_permission_rules(role)
    return roles


def seed_role_permission_rules(role: Role):
    role_defaults = DEFAULT_ROLE_MATRIX.get(role.slug, {})
    for permission_key in PERMISSION_KEYS:
        PermissionRule.objects.get_or_create(
            role=role,
            permission_key=permission_key,
            defaults={"is_allowed": bool(role_defaults.get(permission_key, False))},
        )


def get_user_role(user):
    if not getattr(user, "is_authenticated", False):
        return None
    profile = getattr(user, "profile", None)
    if profile is None:
        profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile.role


def get_effective_permissions(user) -> dict[str, bool]:
    if not getattr(user, "is_authenticated", False):
        return {key: False for key in PERMISSION_KEYS}

    if getattr(user, "is_superuser", False):
        return {key: True for key in PERMISSION_KEYS}

    base = {key: False for key in PERMISSION_KEYS}
    if getattr(user, "is_administrator", False):
        base.update(
            {
                PermissionRule.PermissionKey.MANAGE_USERS: True,
                PermissionRule.PermissionKey.MANAGE_SETTINGS: True,
                PermissionRule.PermissionKey.MANAGE_PROFILES: True,
                PermissionRule.PermissionKey.MANAGE_SCHEDULES: True,
                PermissionRule.PermissionKey.VIEW_SYSTEM_HEALTH: True,
                PermissionRule.PermissionKey.RUN_SCANS: True,
                PermissionRule.PermissionKey.ARCHIVE_RESULTS: True,
                PermissionRule.PermissionKey.GENERATE_REPORTS: True,
            }
        )
    elif getattr(user, "is_operator", False):
        base[PermissionRule.PermissionKey.RUN_SCANS] = True

    role = get_user_role(user)
    if role is not None:
        for rule in role.permission_rules.all():
            base[rule.permission_key] = bool(rule.is_allowed)

    return base


def user_has_permission(user, permission_key: str) -> bool:
    return bool(get_effective_permissions(user).get(permission_key, False))


def can_manage_users(user) -> bool:
    return user_has_permission(user, PermissionRule.PermissionKey.MANAGE_USERS)


def can_manage_settings(user) -> bool:
    return user_has_permission(user, PermissionRule.PermissionKey.MANAGE_SETTINGS)


def can_manage_profiles(user) -> bool:
    return user_has_permission(user, PermissionRule.PermissionKey.MANAGE_PROFILES)


def can_view_system_health(user) -> bool:
    return user_has_permission(user, PermissionRule.PermissionKey.VIEW_SYSTEM_HEALTH)


def build_permission_matrix(roles: Iterable[Role]) -> list[dict]:
    roles = list(roles)
    permission_lookup: dict[tuple[int, str], bool] = {}
    for rule in PermissionRule.objects.filter(role__in=roles):
        permission_lookup[(rule.role_id, rule.permission_key)] = bool(rule.is_allowed)

    rows: list[dict] = []
    for key, label in PermissionRule.PermissionKey.choices:
        values_by_role = {role.id: permission_lookup.get((role.id, key), False) for role in roles}
        rows.append({"permission_key": key, "label": label, "values_by_role": values_by_role})
    return rows
