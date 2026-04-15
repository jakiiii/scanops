from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Max, Q
from django.utils import timezone

from apps.accounts.models import UserLogs
from apps.ops.models import UserProfile

User = get_user_model()


@dataclass(slots=True)
class UserActivitySummary:
    logins_30d: int = 0
    admin_actions_30d: int = 0
    last_seen_at: timezone.datetime | None = None

    @property
    def label(self) -> str:
        if self.logins_30d == 0 and self.admin_actions_30d == 0:
            return "No recent activity"
        return f"{self.logins_30d} login(s), {self.admin_actions_30d} admin action(s)"


def ensure_profile(user) -> UserProfile:
    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={
            "display_name": user.get_full_name() or user.username,
            "is_approved": True,
            "is_internal_operator": True,
        },
    )
    return profile


def _split_display_name(display_name: str) -> tuple[str, str]:
    parts = [p for p in (display_name or "").strip().split(" ") if p]
    if not parts:
        return ("", "")
    if len(parts) == 1:
        return (parts[0], "")
    return (parts[0], " ".join(parts[1:]))


@transaction.atomic
def create_user(payload: dict, *, actor=None):
    username = payload["username"].strip()
    email = payload["email"].strip().lower()
    display_name = (payload.get("display_name") or "").strip()
    first_name, last_name = _split_display_name(display_name)

    user = User.objects.create(
        username=username,
        email=email,
        first_name=first_name,
        last_name=last_name,
        is_active=bool(payload.get("is_active", True)),
        is_operator=True,
    )
    password = (payload.get("new_password") or "").strip()
    if password:
        user.set_password(password)
        user.save(update_fields=["password"])
    else:
        random_password = User.objects.make_random_password()
        user.set_password(random_password)
        user.save(update_fields=["password"])

    profile = ensure_profile(user)
    profile.display_name = display_name or user.get_full_name() or user.username
    profile.role = payload.get("role")
    profile.is_approved = bool(payload.get("is_approved", True))
    profile.is_internal_operator = bool(payload.get("is_internal_operator", True))
    profile.allowed_workspace = (payload.get("allowed_workspace") or "").strip()
    profile.notes = (payload.get("notes") or "").strip()
    profile.force_password_reset = bool(payload.get("force_password_reset", not bool(password)))
    profile.save()
    return user


@transaction.atomic
def update_user(user, payload: dict, *, actor=None):
    display_name = (payload.get("display_name") or "").strip()
    first_name, last_name = _split_display_name(display_name)
    user.username = payload["username"].strip()
    user.email = payload["email"].strip().lower()
    user.first_name = first_name
    user.last_name = last_name
    user.is_active = bool(payload.get("is_active", True))
    user.save()

    new_password = (payload.get("new_password") or "").strip()
    if new_password:
        user.set_password(new_password)
        user.save(update_fields=["password"])

    profile = ensure_profile(user)
    profile.display_name = display_name or user.get_full_name() or user.username
    profile.role = payload.get("role")
    profile.is_approved = bool(payload.get("is_approved", True))
    profile.is_internal_operator = bool(payload.get("is_internal_operator", True))
    profile.allowed_workspace = (payload.get("allowed_workspace") or "").strip()
    profile.notes = (payload.get("notes") or "").strip()
    profile.force_password_reset = bool(payload.get("force_password_reset", False))
    profile.save()
    return user


def set_user_active(user, *, is_active: bool):
    user.is_active = bool(is_active)
    user.save(update_fields=["is_active"])
    return user


def mark_password_reset_required(user, *, required: bool = True):
    profile = ensure_profile(user)
    profile.force_password_reset = bool(required)
    profile.save(update_fields=["force_password_reset", "updated_at"])
    return profile


def summarize_user_activity_bulk(user_ids: list[int]) -> dict[int, UserActivitySummary]:
    summaries = {user_id: UserActivitySummary() for user_id in user_ids}
    if not user_ids:
        return summaries

    since = timezone.now() - timezone.timedelta(days=30)
    logs = (
        UserLogs.objects.filter(user_id__in=user_ids, action_datetime__gte=since)
        .values("user_id")
        .annotate(
            login_count=Count(
                "id",
                filter=Q(
                    action_type__in=[
                        UserLogs.ActionType.LOGIN,
                        UserLogs.ActionType.LOGOUT,
                    ]
                ),
            ),
            admin_count=Count(
                "id",
                filter=Q(
                    action_type__in=[
                        UserLogs.ActionType.ADMIN_CREATE,
                        UserLogs.ActionType.ADMIN_UPDATE,
                        UserLogs.ActionType.ADMIN_DELETE,
                    ]
                ),
            ),
            last_seen=Max("action_datetime"),
        )
    )
    for row in logs:
        summaries[row["user_id"]] = UserActivitySummary(
            logins_30d=row["login_count"] or 0,
            admin_actions_30d=row["admin_count"] or 0,
            last_seen_at=row["last_seen"],
        )
    return summaries
