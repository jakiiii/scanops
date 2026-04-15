from __future__ import annotations

from django import forms

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["target"].queryset = Target.objects.order_by("target_value")
        for field in self.fields.values():
            field.widget.attrs["class"] = "scanops-input"
        self.fields["q"].widget.attrs["placeholder"] = "Search asset name, IP, hostname..."
        self.fields["owner_name"].widget.attrs["placeholder"] = "Owner/team"

