from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.ops.models import PermissionRule, UserProfile
from apps.ops.services import permission_service


class Command(BaseCommand):
    help = "Sync default RBAC roles/capabilities and backfill missing user role assignments."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset-system-defaults",
            action="store_true",
            help="Reset system role permissions to the default matrix.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        roles = permission_service.bootstrap_default_roles()
        permission_service.sync_system_role_permissions(
            overwrite_system_defaults=bool(options.get("reset_system_defaults"))
        )

        stale_rule_count, _ = PermissionRule.objects.exclude(
            permission_key__in=permission_service.PERMISSION_KEYS
        ).delete()

        User = get_user_model()
        profile_created = 0
        role_assigned = 0
        for user in User.objects.all().order_by("id"):
            profile, created = UserProfile.objects.get_or_create(
                user=user,
                defaults={"display_name": user.get_full_name() or user.username},
            )
            if created:
                profile_created += 1

            role = profile.role
            if role is None:
                fallback_slug = permission_service.get_user_role_slug(user) or permission_service.VIEWER
                role = next((item for item in roles if item.slug == fallback_slug), None)
                if role is None:
                    role = next((item for item in roles if item.slug == permission_service.VIEWER), None)
                profile.role = role
                profile.save(update_fields=["role", "updated_at"])
                role_assigned += 1

            if role is not None:
                permission_service.assign_role_to_user(user, role)

        self.stdout.write(
            self.style.SUCCESS(
                "RBAC sync complete "
                f"(roles={len(roles)}, new_profiles={profile_created}, backfilled_roles={role_assigned}, "
                f"removed_stale_rules={stale_rule_count})."
            )
        )
