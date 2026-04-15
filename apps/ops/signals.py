from __future__ import annotations

from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from apps.ops.models import UserProfile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def ensure_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(
            user=instance,
            defaults={
                "display_name": instance.get_full_name() or instance.username,
                "is_approved": True,
                "is_internal_operator": True,
            },
        )


@receiver(user_logged_in)
def update_profile_last_seen(sender, user, request, **kwargs):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.last_seen_at = timezone.now()
    profile.save(update_fields=["last_seen_at", "updated_at"])
