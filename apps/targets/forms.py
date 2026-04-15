from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model
from django.db import models

from apps.core.services.target_validation import validate_target_input
from apps.targets.models import Target

User = get_user_model()


class TargetForm(forms.ModelForm):
    class Meta:
        model = Target
        fields = [
            "name",
            "target_value",
            "target_type",
            "owner",
            "status",
            "tags",
            "notes",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "scanops-input", "placeholder": "Friendly label (optional)"}
            ),
            "target_value": forms.TextInput(
                attrs={"class": "scanops-input", "placeholder": "e.g. 10.10.20.5 or app.internal.local"}
            ),
            "target_type": forms.Select(attrs={"class": "scanops-input"}),
            "owner": forms.Select(attrs={"class": "scanops-input"}),
            "status": forms.Select(attrs={"class": "scanops-input"}),
            "tags": forms.TextInput(
                attrs={"class": "scanops-input", "placeholder": "comma,separated,tags"}
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "scanops-input",
                    "rows": 4,
                    "placeholder": "Operational notes, restrictions, or ownership context",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["owner"].queryset = User.objects.filter(is_active=True).order_by("username")
        self.fields["owner"].required = False
        self._validation_warnings: list[str] = []

    def get_warnings(self) -> list[str]:
        return self._validation_warnings

    def clean_tags(self) -> str:
        raw_tags = (self.cleaned_data.get("tags") or "").strip()
        if not raw_tags:
            return ""
        normalized = ",".join(
            sorted({tag.strip().lower() for tag in raw_tags.split(",") if tag.strip()})
        )
        return normalized

    def clean(self):
        cleaned_data = super().clean()
        target_type = cleaned_data.get("target_type")
        target_value = cleaned_data.get("target_value")
        if not target_type or not target_value:
            return cleaned_data

        validation_result = validate_target_input(target_type=target_type, target_value=target_value)
        if not validation_result.is_valid:
            raise forms.ValidationError(validation_result.errors)

        existing = (
            Target.objects.filter(
                target_type=target_type,
                normalized_value=validation_result.normalized_value,
            )
            .exclude(pk=self.instance.pk)
            .exists()
        )
        if existing:
            raise forms.ValidationError(
                "This target already exists with the same type and value."
            )

        cleaned_data["normalized_value"] = validation_result.normalized_value
        self._validation_warnings = validation_result.warnings
        return cleaned_data

    def save(self, commit=True):
        obj: Target = super().save(commit=False)
        obj.normalized_value = self.cleaned_data["normalized_value"]
        if commit:
            obj.save()
        return obj


class TargetFilterForm(forms.Form):
    q = forms.CharField(required=False, label="Search")
    target_type = forms.ChoiceField(required=False, choices=[("", "All Types")] + list(Target.TargetType.choices))
    status = forms.ChoiceField(required=False, choices=[("", "Any Status")] + list(Target.Status.choices))
    owner = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        empty_label="All Users",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["owner"].queryset = User.objects.filter(is_active=True).order_by("username")
        for field in self.fields.values():
            field.widget.attrs["class"] = "scanops-input"
        self.fields["q"].widget.attrs["placeholder"] = "IP, domain, CIDR, tags..."

    def apply(self, queryset):
        if not self.is_valid():
            return queryset

        q = (self.cleaned_data.get("q") or "").strip()
        target_type = self.cleaned_data.get("target_type") or ""
        status = self.cleaned_data.get("status") or ""
        owner = self.cleaned_data.get("owner")

        if q:
            queryset = queryset.filter(
                models.Q(name__icontains=q)
                | models.Q(target_value__icontains=q)
                | models.Q(tags__icontains=q)
            )
        if target_type:
            queryset = queryset.filter(target_type=target_type)
        if status:
            queryset = queryset.filter(status=status)
        if owner:
            queryset = queryset.filter(owner=owner)
        return queryset
