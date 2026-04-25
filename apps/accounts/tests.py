from __future__ import annotations

import re
from urllib.parse import urlparse

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.ops.services import permission_service


@override_settings(
    SCANOPS_SELF_REGISTRATION_ENABLED=True,
    SCANOPS_SELF_REGISTRATION_REQUIRES_APPROVAL=False,
    SCANOPS_SELF_REGISTRATION_DEFAULT_ROLE="viewer",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class AccountManagementFlowTests(TestCase):
    def setUp(self):
        permission_service.bootstrap_default_roles()
        self.user_model = get_user_model()

    def test_user_registration_assigns_default_viewer_role(self):
        response = self.client.post(
            reverse("accounts:register"),
            data={
                "full_name": "New Analyst",
                "username": "newanalyst",
                "email": "newanalyst@example.com",
                "password1": "Str0ngPass!123",
                "password2": "Str0ngPass!123",
                "phone_number": "+1-555-0100",
                "organization": "Acme Security",
                "job_title": "Junior Analyst",
                "profile_notes": "Created during functional test",
            },
        )
        self.assertRedirects(response, reverse("accounts:register_success"))

        user = self.user_model.objects.get(username="newanalyst")
        self.assertEqual(user.email, "newanalyst@example.com")
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertEqual(user.profile.role.slug, permission_service.VIEWER)
        self.assertEqual(user.profile.allowed_workspace, "Acme Security")
        self.assertIn("Phone: +1-555-0100", user.profile.notes)
        self.assertIn("Job Title: Junior Analyst", user.profile.notes)

    def test_registration_blocks_duplicate_username_and_email(self):
        self.user_model.objects.create_user(
            username="existing",
            email="existing@example.com",
            password="Str0ngPass!123",
        )
        response = self.client.post(
            reverse("accounts:register"),
            data={
                "full_name": "Duplicate User",
                "username": "existing",
                "email": "existing@example.com",
                "password1": "Str0ngPass!123",
                "password2": "Str0ngPass!123",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already in use")

    def test_password_reset_flow_updates_password_and_clears_force_reset(self):
        user = self.user_model.objects.create_user(
            username="resetuser",
            email="resetuser@example.com",
            password="InitialPass!123",
        )
        user.profile.force_password_reset = True
        user.profile.save(update_fields=["force_password_reset", "updated_at"])

        response = self.client.post(reverse("accounts:password_reset"), data={"email": "resetuser@example.com"})
        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)

        email_body = mail.outbox[0].body
        match = re.search(r"http://testserver[^\s]+", email_body)
        self.assertIsNotNone(match)
        reset_path = urlparse(match.group(0)).path

        response = self.client.get(reset_path, follow=True)
        self.assertEqual(response.status_code, 200)
        confirm_path = response.request["PATH_INFO"]

        response = self.client.post(
            confirm_path,
            data={
                "new_password1": "UpdatedPass!123",
                "new_password2": "UpdatedPass!123",
            },
        )
        self.assertRedirects(response, reverse("accounts:password_reset_complete"))

        user.refresh_from_db()
        self.assertFalse(user.profile.force_password_reset)
        self.assertTrue(user.check_password("UpdatedPass!123"))

    def test_password_change_keeps_session_and_changes_password(self):
        user = self.user_model.objects.create_user(
            username="changepassuser",
            email="changepassuser@example.com",
            password="InitialPass!123",
        )
        user.profile.force_password_reset = True
        user.profile.save(update_fields=["force_password_reset", "updated_at"])

        self.client.force_login(user)
        response = self.client.post(
            reverse("accounts:password_change"),
            data={
                "old_password": "InitialPass!123",
                "new_password1": "UltraC0mplex!789",
                "new_password2": "UltraC0mplex!789",
            },
        )
        self.assertRedirects(response, reverse("accounts:password_change_done"))

        session_user_id = self.client.session.get("_auth_user_id")
        self.assertEqual(session_user_id, str(user.pk))

        user.refresh_from_db()
        self.assertFalse(user.profile.force_password_reset)
        self.assertTrue(user.check_password("UltraC0mplex!789"))

        self.client.logout()
        login_response = self.client.post(
            reverse("accounts:login"),
            data={"username": "changepassuser", "password": "UltraC0mplex!789"},
        )
        self.assertEqual(login_response.status_code, 302)
