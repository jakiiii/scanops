from django.db import models
from django.utils.translation import gettext_lazy as _

from django.contrib.auth import get_user_model

User = get_user_model()


class BaseModel(models.Model):
    class StatusChoices(models.TextChoices):
        PUBLISHED = 'PUBLISHED', _('PUBLISHED')
        UNPUBLISHED = 'UNPUBLISHED', _('UNPUBLISHED')
        ARCHIVED = 'ARCHIVED', _('ARCHIVED')

    created_at = models.DateTimeField(
        auto_now_add=True,
        editable=False
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        editable=False
    )
    posted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="issue_posted_user",
        verbose_name=_("রিপোর্টারের নাম")
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="issue_updated_user",
        verbose_name=_("পরিপোর্ট হালনাগাদ কারীর নাম")
    )

    class Meta:
        abstract = True
        app_label = 'base'
