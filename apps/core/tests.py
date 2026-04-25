from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.assets.models import Asset
from apps.notifications.models import Notification
from apps.ops.models import Role
from apps.ops.services import permission_service
from apps.reports.models import GeneratedReport
from apps.scans.models import ScanExecution, ScanProfile, ScanRequest, ScanResult
from apps.targets.models import Target


class UserDataIsolationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        permission_service.bootstrap_default_roles()
        roles = {role.slug: role for role in Role.objects.all()}
        User = get_user_model()

        cls.superadmin = User.objects.create_user(
            username="superadmin_test",
            email="superadmin_test@scanops.local",
            password="TestPass@123",
            is_superuser=True,
            is_staff=True,
            is_administrator=True,
            is_operator=True,
        )
        cls.securityadmin = User.objects.create_user(
            username="securityadmin_test",
            email="securityadmin_test@scanops.local",
            password="TestPass@123",
            is_staff=True,
            is_administrator=True,
            is_operator=True,
        )
        cls.analyst = User.objects.create_user(
            username="analyst1_test",
            email="analyst1_test@scanops.local",
            password="TestPass@123",
            is_operator=True,
        )
        cls.operator = User.objects.create_user(
            username="operator1_test",
            email="operator1_test@scanops.local",
            password="TestPass@123",
            is_operator=True,
        )
        cls.viewer = User.objects.create_user(
            username="viewer1_test",
            email="viewer1_test@scanops.local",
            password="TestPass@123",
        )

        permission_service.assign_role_to_user(cls.superadmin, roles[permission_service.SUPER_ADMIN])
        permission_service.assign_role_to_user(cls.securityadmin, roles[permission_service.SECURITY_ADMIN])
        permission_service.assign_role_to_user(cls.analyst, roles[permission_service.ANALYST])
        permission_service.assign_role_to_user(cls.operator, roles[permission_service.OPERATOR])
        permission_service.assign_role_to_user(cls.viewer, roles[permission_service.VIEWER])

        cls.profile = ScanProfile.objects.create(
            name="Isolation Profile",
            is_system=True,
            is_active=True,
            scan_type=ScanProfile.ScanType.SAFE_BASIC,
            timing_profile=ScanProfile.TimingProfile.NORMAL,
            created_by=cls.superadmin,
        )

        cls.analyst_target = Target.objects.create(
            name="Analyst Target Visible Only",
            target_type=Target.TargetType.IP,
            target_value="10.21.1.10",
            owner=cls.analyst,
            created_by=cls.analyst,
            status=Target.Status.ACTIVE,
        )
        cls.operator_target = Target.objects.create(
            name="Operator Target Visible Only",
            target_type=Target.TargetType.IP,
            target_value="10.22.1.10",
            owner=cls.operator,
            created_by=cls.operator,
            status=Target.Status.ACTIVE,
        )

        cls.analyst_request = ScanRequest.objects.create(
            target=cls.analyst_target,
            profile=cls.profile,
            scan_type=cls.profile.scan_type,
            timing_profile=cls.profile.timing_profile,
            status=ScanRequest.Status.PENDING,
            requested_by=cls.analyst,
        )
        cls.operator_request = ScanRequest.objects.create(
            target=cls.operator_target,
            profile=cls.profile,
            scan_type=cls.profile.scan_type,
            timing_profile=cls.profile.timing_profile,
            status=ScanRequest.Status.PENDING,
            requested_by=cls.operator,
        )

        cls.analyst_execution = ScanExecution.objects.create(
            scan_request=cls.analyst_request,
            status=ScanExecution.Status.COMPLETED,
            queue_status=ScanExecution.QueueStatus.DONE,
            progress_percent=100,
            current_stage="Completed",
            completed_at=timezone.now(),
        )
        cls.operator_execution = ScanExecution.objects.create(
            scan_request=cls.operator_request,
            status=ScanExecution.Status.COMPLETED,
            queue_status=ScanExecution.QueueStatus.DONE,
            progress_percent=100,
            current_stage="Completed",
            completed_at=timezone.now(),
        )

        cls.analyst_result = ScanResult.objects.create(
            execution=cls.analyst_execution,
            target_snapshot=cls.analyst_target.target_value,
            host_status=ScanResult.HostStatus.UP,
            total_open_ports=2,
            total_services_detected=1,
        )
        cls.operator_result = ScanResult.objects.create(
            execution=cls.operator_execution,
            target_snapshot=cls.operator_target.target_value,
            host_status=ScanResult.HostStatus.UP,
            total_open_ports=3,
            total_services_detected=2,
        )

        cls.analyst_report = GeneratedReport.objects.create(
            title="Analyst Private Report",
            report_type=GeneratedReport.ReportType.TECHNICAL_REPORT,
            source_result=cls.analyst_result,
            source_execution=cls.analyst_execution,
            generated_by=cls.analyst,
            format=GeneratedReport.Format.HTML,
            status=GeneratedReport.Status.GENERATED,
            rendered_html="<p>Analyst report</p>",
        )
        cls.operator_report = GeneratedReport.objects.create(
            title="Operator Private Report",
            report_type=GeneratedReport.ReportType.TECHNICAL_REPORT,
            source_result=cls.operator_result,
            source_execution=cls.operator_execution,
            generated_by=cls.operator,
            format=GeneratedReport.Format.HTML,
            status=GeneratedReport.Status.GENERATED,
            rendered_html="<p>Operator report</p>",
        )

        cls.analyst_notification = Notification.objects.create(
            recipient=cls.analyst,
            title="Analyst Notification Only",
            message="Analyst-only event.",
            notification_type=Notification.NotificationType.SYSTEM_ALERT,
            severity=Notification.Severity.INFO,
        )
        cls.operator_notification = Notification.objects.create(
            recipient=cls.operator,
            title="Operator Notification Only",
            message="Operator-only event.",
            notification_type=Notification.NotificationType.SYSTEM_ALERT,
            severity=Notification.Severity.INFO,
        )

        cls.analyst_asset = Asset.objects.create(
            name="Analyst Private Asset",
            target=cls.analyst_target,
            owner=cls.analyst,
            owner_name=cls.analyst.username,
            canonical_identifier="asset-analyst-private",
            status=Asset.Status.ACTIVE,
            risk_level=Asset.RiskLevel.LOW,
            current_open_ports_count=2,
        )
        cls.operator_asset = Asset.objects.create(
            name="Operator Private Asset",
            target=cls.operator_target,
            owner=cls.operator,
            owner_name=cls.operator.username,
            canonical_identifier="asset-operator-private",
            status=Asset.Status.ACTIVE,
            risk_level=Asset.RiskLevel.LOW,
            current_open_ports_count=3,
        )

    def test_operator_cannot_see_analyst_target_in_list_or_detail(self):
        self.client.force_login(self.operator)
        response = self.client.get(reverse("targets:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Operator Target Visible Only")
        self.assertNotContains(response, "Analyst Target Visible Only")

        detail_response = self.client.get(reverse("targets:detail", kwargs={"pk": self.analyst_target.pk}))
        self.assertIn(detail_response.status_code, {403, 404})

    def test_analyst_cannot_access_operator_scan_detail_urls(self):
        self.client.force_login(self.analyst)
        monitor_response = self.client.get(reverse("scans:monitor", kwargs={"pk": self.operator_execution.pk}))
        self.assertIn(monitor_response.status_code, {403, 404})

        result_response = self.client.get(reverse("scans:result-detail", kwargs={"pk": self.operator_result.pk}))
        self.assertIn(result_response.status_code, {403, 404})

    def test_viewer_cannot_create_new_scan(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("scans:new"))
        self.assertEqual(response.status_code, 403)

    def test_notifications_are_scoped_for_non_admin_users(self):
        self.client.force_login(self.analyst)
        list_response = self.client.get(reverse("notifications:list"))
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, "Analyst Notification Only")
        self.assertNotContains(list_response, "Operator Notification Only")

        detail_response = self.client.get(reverse("notifications:detail", kwargs={"pk": self.operator_notification.pk}))
        self.assertIn(detail_response.status_code, {403, 404})

    def test_reports_are_scoped_for_non_admin_users(self):
        self.client.force_login(self.analyst)
        list_response = self.client.get(reverse("reports:list"))
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, "Analyst Private Report")
        self.assertNotContains(list_response, "Operator Private Report")

        detail_response = self.client.get(reverse("reports:detail", kwargs={"pk": self.operator_report.pk}))
        self.assertIn(detail_response.status_code, {403, 404})

    def test_superadmin_can_view_cross_user_data(self):
        self.client.force_login(self.superadmin)

        targets_response = self.client.get(reverse("targets:list"))
        self.assertContains(targets_response, "Analyst Target Visible Only")
        self.assertContains(targets_response, "Operator Target Visible Only")

        running_response = self.client.get(reverse("scans:running"))
        self.assertContains(running_response, self.analyst_execution.execution_id)
        self.assertContains(running_response, self.operator_execution.execution_id)

        reports_response = self.client.get(reverse("reports:list"))
        self.assertContains(reports_response, "Analyst Private Report")
        self.assertContains(reports_response, "Operator Private Report")

    def test_htmx_tables_do_not_leak_cross_user_rows(self):
        self.client.force_login(self.operator)
        targets_partial = self.client.get(reverse("targets:list"), HTTP_HX_REQUEST="true")
        self.assertEqual(targets_partial.status_code, 200)
        self.assertContains(targets_partial, "Operator Target Visible Only")
        self.assertNotContains(targets_partial, "Analyst Target Visible Only")

        self.client.force_login(self.analyst)
        running_partial = self.client.get(reverse("scans:running"), HTTP_HX_REQUEST="true")
        self.assertEqual(running_partial.status_code, 200)
        self.assertContains(running_partial, self.analyst_execution.execution_id)
        self.assertNotContains(running_partial, self.operator_execution.execution_id)

    def test_direct_asset_url_access_is_blocked_for_other_users(self):
        self.client.force_login(self.analyst)
        detail_response = self.client.get(reverse("assets:detail", kwargs={"pk": self.operator_asset.pk}))
        self.assertIn(detail_response.status_code, {403, 404})
