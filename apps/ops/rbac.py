from __future__ import annotations

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q, QuerySet

from apps.ops.services import permission_service


class CapabilityRequiredMixin(LoginRequiredMixin):
    capability_key: str | None = None
    capability_keys: tuple[str, ...] = ()
    any_capability_keys: tuple[str, ...] = ()

    def has_capability(self) -> bool:
        if self.capability_key and not permission_service.user_has_permission(self.request.user, self.capability_key):
            return False
        if self.capability_keys and not all(
            permission_service.user_has_permission(self.request.user, key) for key in self.capability_keys
        ):
            return False
        if self.any_capability_keys and not any(
            permission_service.user_has_permission(self.request.user, key) for key in self.any_capability_keys
        ):
            return False
        return True

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not self.has_capability():
            raise PermissionDenied("You do not have permission to access this resource.")
        return super().dispatch(request, *args, **kwargs)


def require_capability(capability_key: str):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapped(request, *args, **kwargs):
            if not permission_service.user_has_permission(request.user, capability_key):
                raise PermissionDenied("You do not have permission to access this resource.")
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator


def user_has_global_scope(user) -> bool:
    return permission_service.get_user_role_slug(user) in {
        permission_service.SUPER_ADMIN,
        permission_service.SECURITY_ADMIN,
        permission_service.ANALYST,
    } or getattr(user, "is_superuser", False)


def user_is_scoped(user) -> bool:
    return permission_service.is_scoped_role(user)


def scope_queryset_for_user(queryset: QuerySet, user, owner_fields: tuple[str, ...]):
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    if user_has_global_scope(user):
        return queryset

    if not owner_fields:
        return queryset.none()

    predicate = Q()
    for field in owner_fields:
        predicate |= Q(**{field: user})
    return queryset.filter(predicate)


def can_manage_user(actor, target_user) -> bool:
    return permission_service.can_manage_user_account(actor, target_user)
