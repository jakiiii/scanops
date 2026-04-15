from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.ops.models import SystemHealthSnapshot, WorkerStatusSnapshot
from apps.ops.services import app_settings_service, permission_service


class Command(BaseCommand):
    help = "Seed development-safe defaults for Settings/User Management/System Health phase."

    def add_arguments(self, parser):
        parser.add_argument("--with-health", action="store_true", help="Generate sample worker and health snapshots.")

    def handle(self, *args, **options):
        User = get_user_model()
        actor = User.objects.filter(is_active=True).order_by("id").first()

        roles = permission_service.bootstrap_default_roles()
        for category in app_settings_service.SETTINGS_SCHEMA.keys():
            app_settings_service.reset_category_to_defaults(category, user=actor)

        if options["with_health"]:
            now = timezone.now()
            WorkerStatusSnapshot.objects.bulk_create(
                [
                    WorkerStatusSnapshot(
                        worker_name="worker-alpha",
                        status=WorkerStatusSnapshot.Status.ONLINE,
                        active_jobs_count=3,
                        queued_jobs_count=2,
                        failed_jobs_count=0,
                        heartbeat_at=now - timezone.timedelta(seconds=30),
                        metadata_json={"source": "seed"},
                    ),
                    WorkerStatusSnapshot(
                        worker_name="worker-bravo",
                        status=WorkerStatusSnapshot.Status.DEGRADED,
                        active_jobs_count=1,
                        queued_jobs_count=5,
                        failed_jobs_count=2,
                        heartbeat_at=now - timezone.timedelta(minutes=9),
                        metadata_json={"source": "seed"},
                    ),
                    WorkerStatusSnapshot(
                        worker_name="worker-charlie",
                        status=WorkerStatusSnapshot.Status.OFFLINE,
                        active_jobs_count=0,
                        queued_jobs_count=0,
                        failed_jobs_count=3,
                        heartbeat_at=now - timezone.timedelta(minutes=55),
                        metadata_json={"source": "seed"},
                    ),
                ]
            )
            SystemHealthSnapshot.objects.bulk_create(
                [
                    SystemHealthSnapshot(
                        service_name=SystemHealthSnapshot.ServiceName.DJANGO_APP,
                        status=SystemHealthSnapshot.Status.HEALTHY,
                        summary="Seeded healthy app state.",
                        checked_at=now,
                        metadata_json={"source": "seed"},
                    ),
                    SystemHealthSnapshot(
                        service_name=SystemHealthSnapshot.ServiceName.DATABASE,
                        status=SystemHealthSnapshot.Status.HEALTHY,
                        summary="Seeded healthy database state.",
                        checked_at=now,
                        metadata_json={"source": "seed"},
                    ),
                    SystemHealthSnapshot(
                        service_name=SystemHealthSnapshot.ServiceName.NMAP_BINARY,
                        status=SystemHealthSnapshot.Status.WARNING,
                        summary="Seeded warning state for nmap binary.",
                        checked_at=now,
                        metadata_json={"source": "seed"},
                    ),
                ]
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded ops phase defaults: roles={len(roles)}, categories={len(app_settings_service.SETTINGS_SCHEMA)}."
            )
        )
