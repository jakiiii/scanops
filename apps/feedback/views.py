from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.generic import CreateView

from apps.feedback.forms import IssueForm, SuggestionForm
from apps.feedback.models import Issue, Suggestion
from apps.notifications.models import Notification
from apps.notifications.services.notification_service import create_notification
from apps.ops.models import UserProfile
from apps.ops.services import permission_service

User = get_user_model()


def _admin_recipients():
    role_slugs = [permission_service.SUPER_ADMIN, permission_service.SECURITY_ADMIN]
    role_user_ids = UserProfile.objects.filter(
        role__slug__in=role_slugs,
        user__is_active=True,
    ).values_list("user_id", flat=True)
    return User.objects.filter(Q(pk__in=role_user_ids) | Q(is_superuser=True), is_active=True).distinct()


def _notify_admins_for_suggestion(suggestion: Suggestion):
    for recipient in _admin_recipients():
        if suggestion.submitted_by_id and suggestion.submitted_by_id == recipient.id:
            continue
        create_notification(
            recipient=recipient,
            title=f"New suggestion submitted: {suggestion.name}",
            message=f"Suggestion #{suggestion.pk} is awaiting review.",
            notification_type=Notification.NotificationType.SYSTEM_ALERT,
            severity=Notification.Severity.INFO,
            action_url="/admin/feedback/suggestion/",
            metadata={"suggestion_id": suggestion.pk},
        )


def _notify_admins_for_issue(issue: Issue):
    for recipient in _admin_recipients():
        if issue.submitted_by_id and issue.submitted_by_id == recipient.id:
            continue
        create_notification(
            recipient=recipient,
            title=f"New issue reported: {issue.title}",
            message=f"Issue #{issue.pk} was submitted and may require investigation.",
            notification_type=Notification.NotificationType.SYSTEM_ALERT,
            severity=Notification.Severity.WARNING,
            action_url="/admin/feedback/issue/",
            metadata={"issue_id": issue.pk},
        )


class SuggestionCreateView(CreateView):
    model = Suggestion
    form_class = SuggestionForm
    template_name = "feedback/suggestion_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        self.object = form.save(commit=False)
        if self.request.user.is_authenticated:
            self.object.submitted_by = self.request.user
        self.object.save()
        _notify_admins_for_suggestion(self.object)
        messages.success(self.request, "Suggestion submitted successfully. Thank you for your feedback.")
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse("feedback:suggestion")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [
            {"label": "Feedback", "url": ""},
            {"label": "Suggestions", "url": ""},
        ]
        return context


class IssueCreateView(CreateView):
    model = Issue
    form_class = IssueForm
    template_name = "feedback/issue_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        self.object = form.save(commit=False)
        if self.request.user.is_authenticated:
            self.object.submitted_by = self.request.user
        self.object.save()
        _notify_admins_for_issue(self.object)
        messages.success(self.request, "Issue report submitted successfully. Our team will review it.")
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse("feedback:issue")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [
            {"label": "Feedback", "url": ""},
            {"label": "Issues", "url": ""},
        ]
        return context
