from __future__ import annotations

from django import forms

from apps.notifications.models import Notification


class NotificationFilterForm(forms.Form):
    q = forms.CharField(required=False)
    is_read = forms.ChoiceField(
        required=False,
        choices=[("", "All"), ("false", "Unread"), ("true", "Read")],
    )
    notification_type = forms.ChoiceField(
        required=False,
        choices=[("", "All Types")] + list(Notification.NotificationType.choices),
    )
    severity = forms.ChoiceField(
        required=False,
        choices=[("", "All Severities")] + list(Notification.Severity.choices),
    )
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "scanops-input"
        self.fields["q"].widget.attrs["placeholder"] = "Search notifications..."

