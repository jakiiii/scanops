from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.scans.models import ScanExecution, ScanProfile, ScanRequest
from apps.scans.services.execution_service import (
    create_execution_from_request,
    ensure_executions_for_ready_requests,
    simulate_execution_tick,
)
from apps.scans.services.result_service import generate_mock_result_for_execution
from apps.targets.models import Target


class Command(BaseCommand):
    help = "Seed safe development data for running/results/history views."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=12, help="Number of scan requests/executions to ensure.")
        parser.add_argument("--ticks", type=int, default=5, help="Simulation ticks for queued/running executions.")
        parser.add_argument(
            "--no-complete",
            action="store_true",
            help="Do not force executions to completion when generating sample data.",
        )

    def handle(self, *args, **options):
        count = max(1, int(options["count"]))
        ticks = max(0, int(options["ticks"]))
        no_complete = bool(options["no_complete"])

        active_targets = list(Target.objects.filter(status=Target.Status.ACTIVE).order_by("id")[:count])
        if not active_targets:
            self.stdout.write(self.style.WARNING("No active targets found. Create targets first."))
            return

        User = get_user_model()
        default_user = User.objects.filter(is_active=True).order_by("id").first()
        default_profile = ScanProfile.objects.filter(is_active=True).order_by("is_system", "id").first()

        created_requests = 0
        for target in active_targets:
            request = (
                ScanRequest.objects.filter(target=target)
                .order_by("-requested_at")
                .first()
            )
            if request is None:
                request = ScanRequest.objects.create(
                    target=target,
                    profile=default_profile,
                    scan_type=(default_profile.scan_type if default_profile else ScanRequest._meta.get_field("scan_type").default),
                    timing_profile=(default_profile.timing_profile if default_profile else ScanRequest._meta.get_field("timing_profile").default),
                    status=ScanRequest.Status.PENDING,
                    requested_by=default_user,
                    notes="Auto-seeded request for runtime UI testing.",
                )
                created_requests += 1
            if not request.executions.exists():
                create_execution_from_request(request)

        auto_created = ensure_executions_for_ready_requests(limit=count * 2)

        executions = list(
            ScanExecution.objects.select_related("scan_request", "scan_request__target")
            .order_by("-created_at")[: count * 2]
        )

        for execution in executions:
            for _ in range(ticks):
                simulate_execution_tick(execution)
            if not no_complete and execution.status in {ScanExecution.Status.QUEUED, ScanExecution.Status.RUNNING}:
                for _ in range(30):
                    simulate_execution_tick(execution)
                    execution.refresh_from_db(fields=["status"])
                    if execution.status == ScanExecution.Status.COMPLETED:
                        break

        result_count = 0
        for execution in ScanExecution.objects.filter(status=ScanExecution.Status.COMPLETED).select_related("scan_request"):
            if not hasattr(execution, "result"):
                generate_mock_result_for_execution(execution, force=True)
                result_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Runtime seed completed: requests +{created_requests}, executions ensured +{auto_created}, results +{result_count}."
            )
        )
