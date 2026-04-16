from __future__ import annotations

from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from apps.ops.models import Role, UserProfile
from apps.ops.services import permission_service


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def ensure_user_profile(sender, instance, created, **kwargs):
    if created:
        assigned_role = None
        if instance.is_superuser:
            assigned_role = Role.objects.filter(slug=permission_service.SUPER_ADMIN).first()
            if assigned_role is None:
                roles = permission_service.bootstrap_default_roles()
                assigned_role = next((role for role in roles if role.slug == permission_service.SUPER_ADMIN), None)
        else:
            assigned_role = Role.objects.filter(slug=permission_service.VIEWER).first()
            if assigned_role is None:
                roles = permission_service.bootstrap_default_roles()
                assigned_role = next((role for role in roles if role.slug == permission_service.VIEWER), None)
        UserProfile.objects.get_or_create(
            user=instance,
            defaults={
                "display_name": instance.get_full_name() or instance.username,
                "role": assigned_role,
                "is_approved": True,
                "is_internal_operator": True,
            },
        )
        if assigned_role is not None:
            permission_service.assign_role_to_user(instance, assigned_role)


@receiver(user_logged_in)
def update_profile_last_seen(sender, user, request, **kwargs):
    permission_service.get_user_role(user)
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.last_seen_at = timezone.now()
    profile.save(update_fields=["last_seen_at", "updated_at"])
