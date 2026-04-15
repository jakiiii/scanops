from __future__ import annotations

from django import forms
from django.contrib.auth.forms import AuthenticationForm


class OperatorLoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Operator ID",
        widget=forms.TextInput(
            attrs={
                "class": "auth-input",
                "placeholder": "Username or email",
                "autocomplete": "username",
                "autofocus": True,
            }
        ),
    )
    password = forms.CharField(
        label="Security Protocol",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "auth-input",
                "placeholder": "********",
                "autocomplete": "current-password",
            }
        ),
    )
