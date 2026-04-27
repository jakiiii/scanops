from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class UserLogs(models.Model):
    class ActionType(models.TextChoices):
        LOGIN = "login", _("Login")
        LOGOUT = "logout", _("Logout")
        LOGIN_FAILED = "login_failed", _("Failed Login")
        ADMIN_CREATE = "admin_create", _("Admin Create")
        ADMIN_UPDATE = "admin_update", _("Admin Update")
        ADMIN_DELETE = "admin_delete", _("Admin Delete")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="activity_logs",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("User"),
    )
    username_snapshot = models.CharField(
        max_length=150,
        blank=True,
        default="",
        db_index=True,
        verbose_name=_("Username"),
    )
    description = models.CharField(
        max_length=500,
        blank=True,
        default="",
        verbose_name=_("Description"),
    )
    ip_address = models.CharField(
        max_length=45,
        blank=True,
        default="",
        verbose_name=_("IP Address"),
    )
    location = models.CharField(
        max_length=160,
        blank=True,
        default="Unknown",
        verbose_name=_("Location"),
    )
    request_method = models.CharField(
        max_length=10,
        blank=True,
        default="",
        verbose_name=_("Request Method"),
    )
    path = models.CharField(
        max_length=500,
        blank=True,
        default="",
        verbose_name=_("Path"),
    )
    device = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name=_("Device"),
    )
    operating_system = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name=_("Operating System"),
    )
    browser = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name=_("Browser"),
    )
    user_agent = models.TextField(
        blank=True,
        default="",
        verbose_name=_("User Agent"),
    )
    action_type = models.CharField(
        max_length=32,
        choices=ActionType.choices,
        blank=True,
        default="",
        db_index=True,
        verbose_name=_("Action Type"),
    )
    target_model = models.CharField(
        max_length=120,
        blank=True,
        default="",
        verbose_name=_("Target Model"),
    )
    target_object_id = models.CharField(
        max_length=64,
        blank=True,
        default="",
        verbose_name=_("Target Object ID"),
    )
    object_repr = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name=_("Object"),
    )
    is_success = models.BooleanField(
        default=True,
        verbose_name=_("Successful"),
    )
    action_datetime = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        verbose_name=_("Action Datetime"),
    )

    def __str__(self):
        actor = self.username_snapshot or getattr(self.user, "username", "Unknown user")
        return f"{actor} - {self.get_action_type_display() or self.action_type} - {self.action_datetime:%Y-%m-%d %H:%M:%S}"

    class Meta:
        verbose_name = "User Logs"
        verbose_name_plural = "User Logs"
        ordering = ("-action_datetime", "-id")
        db_table = "db_user_logs"
