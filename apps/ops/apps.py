from django.apps import AppConfig


class OpsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ops"
    verbose_name = "Operations Console"

    def ready(self):
        import apps.ops.signals  # noqa: F401
