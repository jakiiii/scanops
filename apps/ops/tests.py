from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import UserLogs
from apps.ops.models import Role
from apps.ops.services import permission_service


class UserLogsAnalyticsAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        permission_service.bootstrap_default_roles()
        roles = {role.slug: role for role in Role.objects.all()}
        user_model = get_user_model()

        cls.super_admin = user_model.objects.create_user(
            username="super_admin_logs",
            email="super_admin_logs@example.com",
            password="TestPass@123",
            is_superuser=True,
            is_staff=True,
        )
        cls.security_admin = user_model.objects.create_user(
            username="security_admin_logs",
            email="security_admin_logs@example.com",
            password="TestPass@123",
            is_staff=True,
        )
        cls.analyst = user_model.objects.create_user(
            username="analyst_logs",
            email="analyst_logs@example.com",
            password="TestPass@123",
        )
        cls.operator = user_model.objects.create_user(
            username="operator_logs",
            email="operator_logs@example.com",
            password="TestPass@123",
        )
        cls.viewer = user_model.objects.create_user(
            username="viewer_logs",
            email="viewer_logs@example.com",
            password="TestPass@123",
        )

        permission_service.assign_role_to_user(cls.super_admin, roles[permission_service.SUPER_ADMIN])
        permission_service.assign_role_to_user(cls.security_admin, roles[permission_service.SECURITY_ADMIN])
        permission_service.assign_role_to_user(cls.analyst, roles[permission_service.ANALYST])
        permission_service.assign_role_to_user(cls.operator, roles[permission_service.OPERATOR])
        permission_service.assign_role_to_user(cls.viewer, roles[permission_service.VIEWER])

        UserLogs.objects.create(
            user=cls.super_admin,
            username_snapshot=cls.super_admin.username,
            action_type=UserLogs.ActionType.LOGIN,
            description="Super admin login success",
            ip_address="10.10.10.10",
            location="United States",
            path="/login/",
            browser="Firefox",
            is_success=True,
        )
        UserLogs.objects.create(
            user=cls.security_admin,
            username_snapshot=cls.security_admin.username,
            action_type=UserLogs.ActionType.LOGOUT,
            description="Security admin logout",
            ip_address="10.10.10.11",
            location="Kazakhstan",
            path="/logout/",
            browser="Chrome",
            is_success=True,
        )
        UserLogs.objects.create(
            user=None,
            username_snapshot="intruder",
            action_type=UserLogs.ActionType.LOGIN_FAILED,
            description="Failed login attempt for intruder",
            ip_address="203.0.113.44",
            path="/login/",
            browser="Unknown",
            is_success=False,
        )

    def test_super_admin_can_access_user_logs_analytics(self):
        self.client.force_login(self.super_admin)
        response = self.client.get(reverse("ops:health-user-logs-analytics"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "User Logs Analytics")
        self.assertContains(response, "Failed login attempt for intruder")
        self.assertContains(response, "Location")
        self.assertContains(response, "United States")
        self.assertContains(response, "Unknown")

    def test_filters_apply_to_recent_logs(self):
        self.client.force_login(self.super_admin)
        response = self.client.get(
            reverse("ops:health-user-logs-analytics"),
            {
                "period": "this_year",
                "action_type": UserLogs.ActionType.LOGIN_FAILED,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Failed login attempt for intruder")
        self.assertNotContains(response, "Super admin login success")

    def test_non_super_admin_roles_get_403(self):
        for user in [self.security_admin, self.analyst, self.operator, self.viewer]:
            self.client.force_login(user)
            response = self.client.get(reverse("ops:health-user-logs-analytics"))
            self.assertEqual(response.status_code, 403)
            self.client.logout()

    def test_anonymous_user_redirected_to_login(self):
        response = self.client.get(reverse("ops:health-user-logs-analytics"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_sidebar_item_visible_only_for_super_admin(self):
        self.client.force_login(self.super_admin)
        super_admin_response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(super_admin_response.status_code, 200)
        self.assertContains(super_admin_response, reverse("ops:health-user-logs-analytics"))
        content = super_admin_response.content.decode()
        nav_start = content.find("scanops-sidebar-nav")
        footer_start = content.find("scanops-sidebar-footer")
        analytics_url = reverse("ops:health-user-logs-analytics")
        analytics_position = content.find(analytics_url)
        self.assertGreater(analytics_position, footer_start)
        self.assertNotIn(analytics_url, content[nav_start:footer_start])

        for user in [self.security_admin, self.analyst, self.operator, self.viewer]:
            self.client.force_login(user)
            response = self.client.get(reverse("dashboard:home"))
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, reverse("ops:health-user-logs-analytics"))

    def test_htmx_request_is_protected_and_returns_partial(self):
        self.client.force_login(self.super_admin)
        allowed_response = self.client.get(
            reverse("ops:health-user-logs-analytics"),
            {"period": "this_year"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(allowed_response.status_code, 200)
        self.assertContains(allowed_response, "Recent Logs")

        self.client.force_login(self.security_admin)
        denied_response = self.client.get(
            reverse("ops:health-user-logs-analytics"),
            {"period": "this_year"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(denied_response.status_code, 403)
