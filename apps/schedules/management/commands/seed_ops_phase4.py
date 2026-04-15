from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.assets.services.asset_service import sync_assets_from_results
from apps.notifications.models import Notification
from apps.notifications.services.notification_service import create_notification, notify_report_generated
from apps.reports.models import GeneratedReport
from apps.reports.services.report_service import generate_report_from_cleaned_data
from apps.scans.models import ScanProfile, ScanResult
from apps.schedules.models import ScanSchedule
from apps.schedules.services.schedule_service import apply_next_run, trigger_schedule_run
from apps.targets.models import Target


class Command(BaseCommand):
    help = "Seed development-safe data for Reports / Schedule / Notifications / Assets pages."

    def add_arguments(self, parser):
        parser.add_argument("--reports", type=int, default=8, help="Number of generated reports to create.")
        parser.add_argument("--schedules", type=int, default=6, help="Number of scan schedules to create/update.")
        parser.add_argument("--notifications", type=int, default=10, help="Number of generic notifications to create.")
        parser.add_argument(
            "--run-now",
            action="store_true",
            help="Trigger run-now for a subset of seeded schedules to populate schedule history.",
        )
        parser.add_argument(
            "--sync-assets",
            action="store_true",
            help="Sync assets from latest scan results as part of seeding.",
        )

    def handle(self, *args, **options):
        reports_target = max(0, int(options["reports"]))
        schedules_target = max(0, int(options["schedules"]))
        notifications_target = max(0, int(options["notifications"]))
        run_now = bool(options["run_now"])
        do_sync_assets = bool(options["sync_assets"])

        User = get_user_model()
        user = User.objects.filter(is_active=True).order_by("id").first()
        if user is None:
            self.stdout.write(self.style.WARNING("No active user found. Create at least one user first."))
            return

        now = timezone.now()
        profile = ScanProfile.objects.filter(is_active=True).order_by("is_system", "id").first()

        reports_created = 0
        comparison_created = 0
        results = list(
            ScanResult.objects.select_related("execution__scan_request__target")
            .order_by("-generated_at")[: max(10, reports_target * 2)]
        )
        report_types = [
            GeneratedReport.ReportType.EXECUTIVE_SUMMARY,
            GeneratedReport.ReportType.TECHNICAL_REPORT,
            GeneratedReport.ReportType.PER_HOST_REPORT,
        ]
        for index, result in enumerate(results[:reports_target], start=1):
            report_type = report_types[index % len(report_types)]
            cleaned_data = {
                "title": f"Seeded Report {result.execution.execution_id}",
                "source_type": "result",
                "report_type": report_type,
                "format": GeneratedReport.Format.HTML,
                "source_result": result,
                "source_execution": None,
                "comparison_left_result": None,
                "comparison_right_result": None,
                "asset": None,
                "include_summary": True,
                "include_ports": True,
                "include_services": True,
                "include_findings": True,
                "include_timeline": False,
                "summary_notes": "Auto-seeded for development UI validation.",
            }
            report = generate_report_from_cleaned_data(cleaned_data, user=user)
            notify_report_generated(report)
            reports_created += 1

        if len(results) >= 2 and reports_target:
            comparison_report = generate_report_from_cleaned_data(
                {
                    "title": f"Seeded Comparison {results[1].execution.execution_id} vs {results[0].execution.execution_id}",
                    "source_type": "comparison",
                    "report_type": GeneratedReport.ReportType.COMPARISON_REPORT,
                    "format": GeneratedReport.Format.HTML,
                    "source_result": None,
                    "source_execution": None,
                    "comparison_left_result": results[1],
                    "comparison_right_result": results[0],
                    "asset": None,
                    "include_summary": True,
                    "include_ports": True,
                    "include_services": False,
                    "include_findings": True,
                    "include_timeline": True,
                    "summary_notes": "Auto-generated comparison for report diff validation.",
                },
                user=user,
            )
            notify_report_generated(comparison_report)
            comparison_created = 1

        schedules_created = 0
        schedules_updated = 0
        run_logs_created = 0
        targets = list(Target.objects.filter(status=Target.Status.ACTIVE).order_by("id")[: max(1, schedules_target)])
        if not targets:
            targets = list(Target.objects.order_by("id")[: max(1, schedules_target)])

        for index, target in enumerate(targets[:schedules_target], start=1):
            name = f"Seeded Schedule {target.pk}"
            schedule, created = ScanSchedule.objects.get_or_create(
                name=name,
                defaults={
                    "target": target,
                    "profile": profile,
                    "scan_type": profile.scan_type if profile else ScanSchedule.ScanType.SAFE_BASIC,
                    "port_input": profile.port_scope if profile else "",
                    "enable_host_discovery": profile.enable_host_discovery if profile else True,
                    "enable_service_detection": profile.enable_service_detection if profile else True,
                    "enable_version_detection": profile.enable_version_detection if profile else False,
                    "enable_os_detection": profile.enable_os_detection if profile else False,
                    "enable_traceroute": profile.enable_traceroute if profile else False,
                    "enable_dns_resolution": profile.enable_dns_resolution if profile else True,
                    "timing_profile": profile.timing_profile if profile else ScanSchedule.TimingProfile.NORMAL,
                    "schedule_type": ScanSchedule.ScheduleType.DAILY if index % 2 else ScanSchedule.ScheduleType.WEEKLY,
                    "start_at": now + timedelta(minutes=5 * index),
                    "end_at": None,
                    "is_enabled": True,
                    "notification_enabled": True,
                    "created_by": user,
                },
            )
            if created:
                schedules_created += 1
            else:
                schedule.target = target
                schedule.profile = profile
                schedule.is_enabled = True
                schedule.notification_enabled = True
                schedule.schedule_type = ScanSchedule.ScheduleType.DAILY if index % 2 else ScanSchedule.ScheduleType.WEEKLY
                schedule.start_at = schedule.start_at or (now + timedelta(minutes=5 * index))
                schedule.save(
                    update_fields=[
                        "target",
                        "profile",
                        "is_enabled",
                        "notification_enabled",
                        "schedule_type",
                        "start_at",
                        "updated_at",
                    ]
                )
                schedules_updated += 1
            apply_next_run(schedule)

            if run_now and index <= 3:
                run_log = trigger_schedule_run(schedule, user=user)
                if run_log.pk:
                    run_logs_created += 1

        generic_notifications_created = 0
        for index in range(notifications_target):
            severity = [
                Notification.Severity.INFO,
                Notification.Severity.SUCCESS,
                Notification.Severity.WARNING,
                Notification.Severity.ERROR,
            ][index % 4]
            ntype = [
                Notification.NotificationType.SYSTEM_ALERT,
                Notification.NotificationType.SCHEDULE_TRIGGERED,
                Notification.NotificationType.REPORT_GENERATED,
                Notification.NotificationType.POLICY_ALERT,
            ][index % 4]
            create_notification(
                recipient=user,
                title=f"Seeded Notification #{index + 1}",
                message="Development sample notification for list/detail UI validation.",
                notification_type=ntype,
                severity=severity,
                action_url="/notifications/",
                metadata={"seeded": True, "index": index + 1},
            )
            generic_notifications_created += 1

        assets_synced = 0
        if do_sync_assets:
            assets_synced = sync_assets_from_results(limit=max(20, reports_target * 4))
            create_notification(
                recipient=user,
                title="Asset sync completed",
                message=f"Synced {assets_synced} assets from available results.",
                notification_type=Notification.NotificationType.ASSET_CHANGED,
                severity=Notification.Severity.INFO,
                action_url="/assets/",
                metadata={"seeded": True, "assets_synced": assets_synced},
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Seed completed: "
                f"reports={reports_created}, comparison={comparison_created}, "
                f"schedules(created={schedules_created}, updated={schedules_updated}), "
                f"run_logs={run_logs_created}, notifications={generic_notifications_created}, "
                f"assets_synced={assets_synced}."
            )
        )
