from __future__ import annotations

import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.feedback.models import Issue, Suggestion
from apps.notifications.models import Notification
from apps.ops.models import Role
from apps.ops.services import permission_service


_TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix="scanops-feedback-tests-")


@override_settings(MEDIA_ROOT=_TEST_MEDIA_ROOT)
class FeedbackFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        permission_service.bootstrap_default_roles()
        roles = {role.slug: role for role in Role.objects.all()}

        User = get_user_model()
        cls.user = User.objects.create_user(
            username="feedback_user",
            email="feedback.user@example.com",
            password="Str0ngPass!123",
            first_name="Feedback",
            last_name="User",
            is_operator=True,
        )
        permission_service.assign_role_to_user(cls.user, roles[permission_service.VIEWER])

        cls.admin_user = User.objects.create_superuser(
            username="feedback_admin",
            email="feedback.admin@example.com",
            password="Str0ngPass!123",
        )
        permission_service.assign_role_to_user(cls.admin_user, roles[permission_service.SUPER_ADMIN])

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_TEST_MEDIA_ROOT, ignore_errors=True)

    def test_suggestion_page_is_public(self):
        response = self.client.get(reverse("feedback:suggestion"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Submit Suggestion")

    def test_anonymous_can_submit_suggestion(self):
        Notification.objects.all().delete()
        response = self.client.post(
            reverse("feedback:suggestion"),
            data={
                "name": "Public Visitor",
                "email": "visitor@example.com",
                "suggestion": "Please add stronger queue diagnostics.",
            },
            follow=False,
        )
        self.assertRedirects(response, reverse("feedback:suggestion"), fetch_redirect_response=False)

        suggestion = Suggestion.objects.get(email="visitor@example.com")
        self.assertEqual(suggestion.name, "Public Visitor")
        self.assertIsNone(suggestion.submitted_by)
        self.assertEqual(suggestion.status, Suggestion.Status.NEW)

        self.assertTrue(
            Notification.objects.filter(
                recipient=self.admin_user,
                title__icontains="New suggestion submitted",
            ).exists()
        )

    def test_authenticated_suggestion_prefill_and_submission_sets_submitted_by(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("feedback:suggestion"))
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(form.fields["name"].initial, "Feedback User")
        self.assertEqual(form.fields["email"].initial, self.user.email)

        post_response = self.client.post(
            reverse("feedback:suggestion"),
            data={
                "name": "Feedback User",
                "email": self.user.email,
                "suggestion": "Add per-module submission analytics.",
            },
            follow=False,
        )
        self.assertRedirects(post_response, reverse("feedback:suggestion"), fetch_redirect_response=False)
        created = Suggestion.objects.get(suggestion="Add per-module submission analytics.")
        self.assertEqual(created.submitted_by, self.user)

    def test_authenticated_can_submit_issue_with_valid_image_attachment(self):
        self.client.force_login(self.user)
        Notification.objects.all().delete()

        attachment = SimpleUploadedFile(
            "ui-bug.png",
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR",
            content_type="image/png",
        )
        response = self.client.post(
            reverse("feedback:issue"),
            data={
                "title": "Result table alignment issue",
                "email": self.user.email,
                "description": "Columns overlap on smaller screens after filtering.",
                "attachment": attachment,
            },
            follow=False,
        )
        self.assertRedirects(response, reverse("feedback:issue"), fetch_redirect_response=False)

        issue = Issue.objects.get(title="Result table alignment issue")
        self.assertEqual(issue.submitted_by, self.user)
        self.assertTrue(issue.attachment.name.startswith("feedback/issues/"))
        self.assertEqual(issue.status, Issue.Status.NEW)

        self.assertTrue(
            Notification.objects.filter(
                recipient=self.admin_user,
                title__icontains="New issue reported",
            ).exists()
        )

    def test_issue_rejects_unsupported_attachment_type(self):
        invalid_attachment = SimpleUploadedFile(
            "payload.exe",
            b"MZ\x00\x00",
            content_type="application/octet-stream",
        )
        response = self.client.post(
            reverse("feedback:issue"),
            data={
                "title": "Invalid upload test",
                "email": "visitor@example.com",
                "description": "The form should reject this file type.",
                "attachment": invalid_attachment,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unsupported file type")
        self.assertFalse(Issue.objects.filter(title="Invalid upload test").exists())

    def test_issue_rejects_file_larger_than_25mb(self):
        large_attachment = SimpleUploadedFile(
            "oversized.mp4",
            b"0" * (25 * 1024 * 1024 + 1),
            content_type="video/mp4",
        )
        response = self.client.post(
            reverse("feedback:issue"),
            data={
                "title": "Large upload test",
                "email": "visitor@example.com",
                "description": "The form should reject oversized files.",
                "attachment": large_attachment,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Attachment is too large")
        self.assertFalse(Issue.objects.filter(title="Large upload test").exists())

    def test_sidebar_bottom_contains_feedback_links_for_anonymous_and_authenticated_users(self):
        doc_url = reverse("core:documentation")
        suggestion_url = reverse("feedback:suggestion")
        issue_url = reverse("feedback:issue")

        anonymous_response = self.client.get(doc_url)
        self.assertContains(anonymous_response, f'href="{suggestion_url}"')
        self.assertContains(anonymous_response, f'href="{issue_url}"')

        self.client.force_login(self.user)
        authenticated_response = self.client.get(doc_url)
        self.assertContains(authenticated_response, f'href="{suggestion_url}"')
        self.assertContains(authenticated_response, f'href="{issue_url}"')

        content = authenticated_response.content.decode("utf-8")
        read_docs_link = f'href="{doc_url}"'
        change_password_link = f'href="{reverse("accounts:password_change")}"'
        self.assertLess(content.index(read_docs_link), content.index(f'href="{suggestion_url}"'))
        self.assertLess(content.index(f'href="{suggestion_url}"'), content.index(f'href="{issue_url}"'))
        self.assertLess(content.index(f'href="{issue_url}"'), content.index(change_password_link))
