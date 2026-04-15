from __future__ import annotations

from django.db.models import Q

from apps.scans.models import ScanProfile


def list_admin_profiles(*, q: str = "", profile_type: str = "", active: str = "", owner_id: int | None = None):
    queryset = ScanProfile.objects.select_related("created_by").order_by("is_system", "name")
    if q:
        queryset = queryset.filter(
            Q(name__icontains=q)
            | Q(description__icontains=q)
            | Q(created_by__username__icontains=q)
        )
    if profile_type == "system":
        queryset = queryset.filter(is_system=True)
    elif profile_type == "shared":
        queryset = queryset.filter(is_system=False)

    if active == "true":
        queryset = queryset.filter(is_active=True)
    elif active == "false":
        queryset = queryset.filter(is_active=False)

    if owner_id:
        queryset = queryset.filter(created_by_id=owner_id)
    return queryset


def summarize_profiles(queryset):
    return {
        "total": queryset.count(),
        "system": queryset.filter(is_system=True).count(),
        "shared": queryset.filter(is_system=False).count(),
        "active": queryset.filter(is_active=True).count(),
    }


def publish_profile(profile: ScanProfile):
    profile.is_active = True
    profile.save(update_fields=["is_active", "updated_at"])
    return profile


def disable_profile(profile: ScanProfile):
    profile.is_active = False
    profile.save(update_fields=["is_active", "updated_at"])
    return profile


def delete_profile(profile: ScanProfile):
    if profile.is_system:
        raise ValueError("System profiles cannot be deleted.")
    profile.delete()
