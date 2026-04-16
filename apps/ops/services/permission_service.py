from __future__ import annotations

from typing import Iterable

from apps.ops.models import PermissionRule, Role, UserProfile


SUPER_ADMIN = "super_admin"
SECURITY_ADMIN = "security_admin"
ANALYST = "analyst"
OPERATOR = "operator"
VIEWER = "viewer"

ROLE_SLUGS = (SUPER_ADMIN, SECURITY_ADMIN, ANALYST, OPERATOR, VIEWER)
ROLE_PRIORITY = {
    SUPER_ADMIN: 50,
    SECURITY_ADMIN: 40,
    ANALYST: 30,
    OPERATOR: 20,
    VIEWER: 10,
}

PERMISSION_KEYS = [choice for choice, _ in PermissionRule.PermissionKey.choices]


def _allow_all() -> dict[str, bool]:
    return {key: True for key in PERMISSION_KEYS}


def _allow(*keys: str) -> dict[str, bool]:
    payload = {key: False for key in PERMISSION_KEYS}
    for key in keys:
        payload[key] = True
    return payload


DEFAULT_ROLE_MATRIX: dict[str, dict[str, bool]] = {
    SUPER_ADMIN: _allow_all(),
    SECURITY_ADMIN: _allow(
        PermissionRule.PermissionKey.VIEW_DASHBOARD,
        PermissionRule.PermissionKey.VIEW_TARGETS,
        PermissionRule.PermissionKey.MANAGE_TARGETS,
        PermissionRule.PermissionKey.VIEW_SCANS,
        PermissionRule.PermissionKey.CREATE_SCAN_REQUEST,
        PermissionRule.PermissionKey.CONTROL_SCAN_EXECUTIONS,
        PermissionRule.PermissionKey.VIEW_RESULTS,
        PermissionRule.PermissionKey.COMPARE_RESULTS,
        PermissionRule.PermissionKey.VIEW_HISTORY,
        PermissionRule.PermissionKey.MANAGE_HISTORY,
        PermissionRule.PermissionKey.VIEW_REPORTS,
        PermissionRule.PermissionKey.GENERATE_REPORTS,
        PermissionRule.PermissionKey.MANAGE_REPORTS,
        PermissionRule.PermissionKey.VIEW_SCHEDULES,
        PermissionRule.PermissionKey.MANAGE_SCHEDULES,
        PermissionRule.PermissionKey.VIEW_NOTIFICATIONS,
        PermissionRule.PermissionKey.VIEW_ASSETS,
        PermissionRule.PermissionKey.MANAGE_ASSETS,
        PermissionRule.PermissionKey.MANAGE_USERS,
        PermissionRule.PermissionKey.MANAGE_PROFILES,
        PermissionRule.PermissionKey.VIEW_SYSTEM_HEALTH,
    ),
    ANALYST: _allow(
        PermissionRule.PermissionKey.VIEW_DASHBOARD,
        PermissionRule.PermissionKey.VIEW_TARGETS,
        PermissionRule.PermissionKey.VIEW_SCANS,
        PermissionRule.PermissionKey.CREATE_SCAN_REQUEST,
        PermissionRule.PermissionKey.VIEW_RESULTS,
        PermissionRule.PermissionKey.COMPARE_RESULTS,
        PermissionRule.PermissionKey.VIEW_HISTORY,
        PermissionRule.PermissionKey.VIEW_REPORTS,
        PermissionRule.PermissionKey.GENERATE_REPORTS,
        PermissionRule.PermissionKey.VIEW_NOTIFICATIONS,
        PermissionRule.PermissionKey.VIEW_ASSETS,
    ),
    OPERATOR: _allow(
        PermissionRule.PermissionKey.VIEW_DASHBOARD,
        PermissionRule.PermissionKey.VIEW_TARGETS,
        PermissionRule.PermissionKey.VIEW_SCANS,
        PermissionRule.PermissionKey.CREATE_SCAN_REQUEST,
        PermissionRule.PermissionKey.CONTROL_SCAN_EXECUTIONS,
        PermissionRule.PermissionKey.VIEW_RESULTS,
        PermissionRule.PermissionKey.COMPARE_RESULTS,
        PermissionRule.PermissionKey.VIEW_HISTORY,
        PermissionRule.PermissionKey.VIEW_NOTIFICATIONS,
    ),
    VIEWER: _allow(
        PermissionRule.PermissionKey.VIEW_DASHBOARD,
        PermissionRule.PermissionKey.VIEW_TARGETS,
        PermissionRule.PermissionKey.VIEW_SCANS,
        PermissionRule.PermissionKey.VIEW_RESULTS,
        PermissionRule.PermissionKey.VIEW_HISTORY,
        PermissionRule.PermissionKey.VIEW_REPORTS,
        PermissionRule.PermissionKey.VIEW_NOTIFICATIONS,
        PermissionRule.PermissionKey.VIEW_ASSETS,
    ),
}

DEFAULT_ROLES = (
    ("Super Admin", SUPER_ADMIN, "Platform-level administrative authority.", True),
    ("Security Admin", SECURITY_ADMIN, "Security governance and policy administration.", True),
    ("Analyst", ANALYST, "Investigation and analysis workflows.", True),
    ("Operator", OPERATOR, "Operational scan execution role.", True),
    ("Viewer", VIEWER, "Read-only role for approved observers.", True),
)


def _sync_legacy_flags(user, role_slug: str):
    user.is_administrator = role_slug in {SUPER_ADMIN, SECURITY_ADMIN}
    user.is_operator = role_slug in {SUPER_ADMIN, SECURITY_ADMIN, ANALYST, OPERATOR}
    user.is_staff = role_slug in {SUPER_ADMIN, SECURITY_ADMIN} or getattr(user, "is_superuser", False)


def bootstrap_default_roles() -> list[Role]:
    roles: list[Role] = []
    for name, slug, description, is_system in DEFAULT_ROLES:
        role, _ = Role.objects.get_or_create(
            slug=slug,
            defaults={"name": name, "description": description, "is_system": is_system},
        )
        changed_fields: list[str] = []
        if role.name != name:
            role.name = name
            changed_fields.append("name")
        if role.description != description:
            role.description = description
            changed_fields.append("description")
        if role.is_system != is_system:
            role.is_system = is_system
            changed_fields.append("is_system")
        if changed_fields:
            role.save(update_fields=[*changed_fields, "updated_at"])
        seed_role_permission_rules(role)
        roles.append(role)
    return roles


def seed_role_permission_rules(role: Role):
    role_defaults = DEFAULT_ROLE_MATRIX.get(role.slug, {})
    valid_keys = set(PERMISSION_KEYS)
    role.permission_rules.exclude(permission_key__in=valid_keys).delete()

    for permission_key in PERMISSION_KEYS:
        PermissionRule.objects.get_or_create(
            role=role,
            permission_key=permission_key,
            defaults={"is_allowed": bool(role_defaults.get(permission_key, False))},
        )


def sync_system_role_permissions(*, overwrite_system_defaults: bool = False):
    role_defaults = {slug: values for slug, values in DEFAULT_ROLE_MATRIX.items()}
    for role in Role.objects.filter(slug__in=ROLE_SLUGS):
        seed_role_permission_rules(role)
        if overwrite_system_defaults:
            defaults = role_defaults.get(role.slug, {})
            for key, should_allow in defaults.items():
                rule = role.permission_rules.filter(permission_key=key).first()
                if rule and rule.is_allowed != should_allow:
                    rule.is_allowed = should_allow
                    rule.save(update_fields=["is_allowed", "updated_at"])


def _default_role_slug_from_legacy_flags(user) -> str:
    if getattr(user, "is_superuser", False):
        return SUPER_ADMIN
    if getattr(user, "is_administrator", False):
        return SECURITY_ADMIN
    if getattr(user, "is_operator", False):
        return OPERATOR
    return VIEWER


def get_user_role(user):
    if not getattr(user, "is_authenticated", False):
        return None
    cached = getattr(user, "_scanops_role_cache", None)
    if cached is not None:
        return cached
    profile, _ = UserProfile.objects.select_related("role").get_or_create(
        user=user,
        defaults={"display_name": user.get_full_name() or user.username},
    )
    if profile.role_id:
        user._scanops_role_cache = profile.role
        return profile.role

    fallback_slug = _default_role_slug_from_legacy_flags(user)
    fallback_role = Role.objects.filter(slug=fallback_slug).first()
    if fallback_role is None:
        roles = bootstrap_default_roles()
        fallback_role = next((role for role in roles if role.slug == fallback_slug), None)
    if fallback_role is not None:
        profile.role = fallback_role
        profile.save(update_fields=["role", "updated_at"])
        _sync_legacy_flags(user, fallback_role.slug)
        user.save(update_fields=["is_administrator", "is_operator", "is_staff"])
    user._scanops_role_cache = profile.role
    return profile.role


def get_user_role_slug(user) -> str | None:
    role = get_user_role(user)
    if role is not None:
        return role.slug
    if not getattr(user, "is_authenticated", False):
        return None
    return _default_role_slug_from_legacy_flags(user)


def get_user_role_name(user) -> str:
    role = get_user_role(user)
    if role is not None:
        return role.name
    slug = get_user_role_slug(user)
    role_map = {
        SUPER_ADMIN: "Super Admin",
        SECURITY_ADMIN: "Security Admin",
        ANALYST: "Analyst",
        OPERATOR: "Operator",
        VIEWER: "Viewer",
    }
    return role_map.get(slug or "", "Unassigned")


def is_super_admin(user) -> bool:
    return get_user_role_slug(user) == SUPER_ADMIN


def is_security_admin(user) -> bool:
    return get_user_role_slug(user) == SECURITY_ADMIN


def is_analyst(user) -> bool:
    return get_user_role_slug(user) == ANALYST


def is_operator(user) -> bool:
    return get_user_role_slug(user) == OPERATOR


def is_viewer(user) -> bool:
    return get_user_role_slug(user) == VIEWER


def is_scoped_role(user) -> bool:
    return get_user_role_slug(user) in {OPERATOR, VIEWER}


def role_priority(user) -> int:
    return ROLE_PRIORITY.get(get_user_role_slug(user) or "", 0)


def get_effective_permissions(user) -> dict[str, bool]:
    base = {key: False for key in PERMISSION_KEYS}
    if not getattr(user, "is_authenticated", False):
        return base
    cached = getattr(user, "_scanops_permission_cache", None)
    if isinstance(cached, dict):
        return dict(cached)

    role_slug = get_user_role_slug(user)
    if role_slug and role_slug in DEFAULT_ROLE_MATRIX:
        base.update(DEFAULT_ROLE_MATRIX[role_slug])

    if getattr(user, "is_superuser", False):
        return {key: True for key in PERMISSION_KEYS}

    role = get_user_role(user)
    if role is not None:
        for rule in role.permission_rules.all():
            if rule.permission_key in base:
                base[rule.permission_key] = bool(rule.is_allowed)
    user._scanops_permission_cache = dict(base)
    return base


def user_has_permission(user, permission_key: str) -> bool:
    return bool(get_effective_permissions(user).get(permission_key, False))


def can_manage_users(user) -> bool:
    return user_has_permission(user, PermissionRule.PermissionKey.MANAGE_USERS)


def can_manage_settings(user) -> bool:
    return user_has_permission(user, PermissionRule.PermissionKey.MANAGE_SETTINGS)


def can_manage_profiles(user) -> bool:
    return user_has_permission(user, PermissionRule.PermissionKey.MANAGE_PROFILES)


def can_manage_roles(user) -> bool:
    return user_has_permission(user, PermissionRule.PermissionKey.MANAGE_ROLES)


def can_view_system_health(user) -> bool:
    return user_has_permission(user, PermissionRule.PermissionKey.VIEW_SYSTEM_HEALTH)


def get_assignable_role_slugs(actor) -> set[str]:
    if not getattr(actor, "is_authenticated", False) or not can_manage_users(actor):
        return set()
    actor_slug = get_user_role_slug(actor)
    if actor_slug == SUPER_ADMIN or getattr(actor, "is_superuser", False):
        return set(ROLE_SLUGS)
    if actor_slug == SECURITY_ADMIN:
        return {ANALYST, OPERATOR, VIEWER}
    return set()


def get_assignable_roles(actor):
    allowed = get_assignable_role_slugs(actor)
    if not allowed:
        return Role.objects.none()
    return Role.objects.filter(slug__in=allowed).order_by("name")


def can_assign_role(actor, role: Role | None) -> bool:
    if role is None:
        return True
    return role.slug in get_assignable_role_slugs(actor)


def can_manage_user_account(actor, target_user) -> bool:
    if not can_manage_users(actor):
        return False
    if getattr(actor, "is_superuser", False):
        return True

    actor_slug = get_user_role_slug(actor)
    target_slug = get_user_role_slug(target_user)

    if target_slug == SUPER_ADMIN or getattr(target_user, "is_superuser", False):
        return False
    if actor_slug == SECURITY_ADMIN and target_slug == SECURITY_ADMIN and actor.pk != target_user.pk:
        return False
    return True


def assign_role_to_user(user, role: Role | None):
    for attr in ("_scanops_role_cache", "_scanops_permission_cache"):
        if hasattr(user, attr):
            delattr(user, attr)
    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={"display_name": user.get_full_name() or user.username},
    )
    if profile.role_id != getattr(role, "id", None):
        profile.role = role
        profile.save(update_fields=["role", "updated_at"])

    effective_slug = role.slug if role else _default_role_slug_from_legacy_flags(user)
    _sync_legacy_flags(user, effective_slug)
    user.save(update_fields=["is_administrator", "is_operator", "is_staff"])


def backfill_missing_roles(default_slug: str = VIEWER) -> int:
    default_role = Role.objects.filter(slug=default_slug).first()
    if default_role is None:
        roles = bootstrap_default_roles()
        default_role = next((role for role in roles if role.slug == default_slug), None)
    if default_role is None:
        return 0

    updated = 0
    for profile in UserProfile.objects.select_related("user", "role").filter(role__isnull=True):
        profile.role = default_role
        profile.save(update_fields=["role", "updated_at"])
        _sync_legacy_flags(profile.user, default_role.slug)
        profile.user.save(update_fields=["is_administrator", "is_operator", "is_staff"])
        updated += 1
    return updated


def build_permission_matrix(roles: Iterable[Role]) -> list[dict]:
    roles = list(roles)
    permission_lookup: dict[tuple[int, str], bool] = {}
    for rule in PermissionRule.objects.filter(role__in=roles):
        if rule.permission_key in PERMISSION_KEYS:
            permission_lookup[(rule.role_id, rule.permission_key)] = bool(rule.is_allowed)

    rows: list[dict] = []
    for key, label in PermissionRule.PermissionKey.choices:
        values_by_role = {role.id: permission_lookup.get((role.id, key), False) for role in roles}
        rows.append({"permission_key": key, "label": label, "values_by_role": values_by_role})
    return rows


def user_role_snapshot(user) -> dict[str, str]:
    role = get_user_role(user)
    if role is not None:
        return {"slug": role.slug, "name": role.name}
    role_slug = get_user_role_slug(user)
    return {"slug": role_slug or "", "name": get_user_role_name(user)}
