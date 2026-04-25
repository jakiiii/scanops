from __future__ import annotations

from django import forms

from apps.ops.services import data_visibility_service
from apps.assets.models import Asset
from apps.targets.models import Target


class AssetFilterForm(forms.Form):
    q = forms.CharField(required=False)
    target = forms.ModelChoiceField(queryset=Target.objects.none(), required=False, empty_label="All Networks/Targets")
    owner_name = forms.CharField(required=False)
    risk_level = forms.ChoiceField(
        required=False,
        choices=[("", "All Risk Levels")] + list(Asset.RiskLevel.choices),
    )
    status = forms.ChoiceField(
        required=False,
        choices=[("", "All Statuses")] + list(Asset.Status.choices),
    )
    last_seen_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    last_seen_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["target"].queryset = Target.objects.order_by("target_value")
        if user is not None:
            self.fields["target"].queryset = data_visibility_service.get_user_visible_targets(
                user,
                queryset=self.fields["target"].queryset,
            )
        for field in self.fields.values():
            field.widget.attrs["class"] = "scanops-input"
        self.fields["q"].widget.attrs["placeholder"] = "Search asset name, IP, hostname..."
        self.fields["owner_name"].widget.attrs["placeholder"] = "Owner/team"
