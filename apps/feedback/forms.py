from __future__ import annotations

from django import forms

from apps.feedback.models import Issue, Suggestion


class SuggestionForm(forms.ModelForm):
    class Meta:
        model = Suggestion
        fields = ("name", "email", "suggestion")
        widgets = {
            "name": forms.TextInput(attrs={"class": "scanops-input", "placeholder": "Your name"}),
            "email": forms.EmailInput(attrs={"class": "scanops-input", "placeholder": "you@example.com"}),
            "suggestion": forms.Textarea(
                attrs={
                    "class": "scanops-input",
                    "rows": 6,
                    "placeholder": "Share your improvement idea for ScanOps...",
                }
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None and getattr(user, "is_authenticated", False):
            full_name = user.get_full_name().strip()
            self.fields["name"].initial = full_name or user.username
            self.fields["email"].initial = user.email

    def clean_suggestion(self):
        value = (self.cleaned_data.get("suggestion") or "").strip()
        if not value:
            raise forms.ValidationError("Suggestion is required.")
        if len(value) > 5000:
            raise forms.ValidationError("Suggestion is too long (maximum 5000 characters).")
        return value


class IssueForm(forms.ModelForm):
    class Meta:
        model = Issue
        fields = ("title", "email", "attachment", "description")
        widgets = {
            "title": forms.TextInput(attrs={"class": "scanops-input", "placeholder": "Issue title"}),
            "email": forms.EmailInput(attrs={"class": "scanops-input", "placeholder": "you@example.com"}),
            "attachment": forms.ClearableFileInput(
                attrs={"class": "scanops-input", "accept": ".jpg,.jpeg,.png,.webp,.mp4,.webm,.mov"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "scanops-input",
                    "rows": 7,
                    "placeholder": "Describe what happened, expected behavior, and observed behavior.",
                }
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None and getattr(user, "is_authenticated", False):
            self.fields["email"].initial = user.email

    def clean_title(self):
        value = (self.cleaned_data.get("title") or "").strip()
        if not value:
            raise forms.ValidationError("Title is required.")
        if len(value) > 200:
            raise forms.ValidationError("Title is too long (maximum 200 characters).")
        return value

    def clean_description(self):
        value = (self.cleaned_data.get("description") or "").strip()
        if not value:
            raise forms.ValidationError("Description is required.")
        if len(value) > 10000:
            raise forms.ValidationError("Description is too long (maximum 10000 characters).")
        return value

