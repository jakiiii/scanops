from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.schedules.models import ScanSchedule
from apps.targets.models import Target


class ScheduleAccessTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.admin = self.user_model.objects.create_user(
            username="scheduleadmin",
            email="scheduleadmin@example.com",
            password="AdminPass!123",
            is_superuser=True,
            is_staff=True,
        )
        self.user_a = self.user_model.objects.create_user(
            username="schedulea",
            email="schedulea@example.com",
            password="UserPass!123",
        )
        self.user_b = self.user_model.objects.create_user(
            username="scheduleb",
            email="scheduleb@example.com",
            password="UserPass!123",
        )

        self.target_a = Target.objects.create(
            name="Target A",
            target_value="10.10.10.10",
            target_type=Target.TargetType.IP,
            owner=self.user_a,
            created_by=self.user_a,
        )
        self.target_b = Target.objects.create(
            name="Target B",
            target_value="10.10.10.11",
            target_type=Target.TargetType.IP,
            owner=self.user_b,
            created_by=self.user_b,
        )

        start_at = timezone.now() + timedelta(days=1)
        self.private_a = ScanSchedule.objects.create(
            name="Private A",
            target=self.target_a,
            start_at=start_at,
            schedule_type=ScanSchedule.ScheduleType.DAILY,
            created_by=self.user_a,
            is_public=False,
        )
        self.public_a = ScanSchedule.objects.create(
            name="Public A",
            target=self.target_a,
            start_at=start_at,
            schedule_type=ScanSchedule.ScheduleType.DAILY,
            created_by=self.user_a,
            is_public=True,
        )
        self.private_b = ScanSchedule.objects.create(
            name="Private B",
            target=self.target_b,
            start_at=start_at,
            schedule_type=ScanSchedule.ScheduleType.DAILY,
            created_by=self.user_b,
            is_public=False,
        )

    def test_visitor_can_only_see_public_schedules(self):
        response = self.client.get(reverse("schedules:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Public A")
        self.assertNotContains(response, "Private A")
        self.assertNotContains(response, "Private B")

    def test_visitor_private_schedule_detail_is_blocked(self):
        private_response = self.client.get(reverse("schedules:detail", kwargs={"pk": self.private_a.pk}))
        self.assertEqual(private_response.status_code, 404)

        public_response = self.client.get(reverse("schedules:detail", kwargs={"pk": self.public_a.pk}))
        self.assertEqual(public_response.status_code, 200)
        self.assertContains(public_response, "Public mode")
        self.assertContains(public_response, "Protected Target")
        self.assertNotContains(public_response, self.target_a.target_value)

    def test_authenticated_user_sees_own_plus_public_schedules(self):
        self.client.force_login(self.user_b)
        response = self.client.get(reverse("schedules:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Private B")
        self.assertContains(response, "Public A")
        self.assertNotContains(response, "Private A")

    def test_authenticated_user_cannot_manage_other_users_private_schedule(self):
        self.client.force_login(self.user_b)

        edit_response = self.client.get(reverse("schedules:edit", kwargs={"pk": self.private_a.pk}))
        self.assertEqual(edit_response.status_code, 404)

        toggle_response = self.client.post(reverse("schedules:toggle", kwargs={"pk": self.private_a.pk}))
        self.assertEqual(toggle_response.status_code, 404)

    def test_admin_can_see_all_schedules(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("schedules:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Private A")
        self.assertContains(response, "Private B")
        self.assertContains(response, "Public A")

    def test_htmx_schedule_list_does_not_leak_private_data_for_visitor(self):
        response = self.client.get(reverse("schedules:list"), HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Public A")
        self.assertNotContains(response, "Private A")
        self.assertNotContains(response, "Private B")
        self.assertNotContains(response, self.target_a.target_value)

    def test_authenticated_user_can_create_schedule_and_visitor_cannot(self):
        visitor_response = self.client.get(reverse("schedules:create"))
        self.assertEqual(visitor_response.status_code, 302)
        self.assertIn(reverse("accounts:login"), visitor_response["Location"])

        self.client.force_login(self.user_b)
        start_at = timezone.localtime(timezone.now() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")
        response = self.client.post(
            reverse("schedules:create"),
            data={
                "name": "User B Public Schedule",
                "target": str(self.target_b.pk),
                "profile": "",
                "scan_type": ScanSchedule.ScanType.SAFE_BASIC,
                "port_input": "",
                "enable_host_discovery": "on",
                "enable_service_detection": "on",
                "enable_dns_resolution": "on",
                "timing_profile": ScanSchedule.TimingProfile.NORMAL,
                "schedule_type": ScanSchedule.ScheduleType.DAILY,
                "recurrence_rule": "",
                "start_at": start_at,
                "end_at": "",
                "is_public": "on",
                "is_enabled": "on",
                "notification_enabled": "on",
            },
        )
        created = ScanSchedule.objects.get(name="User B Public Schedule")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(created.created_by, self.user_b)
        self.assertTrue(created.is_public)
