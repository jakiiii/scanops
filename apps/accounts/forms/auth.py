from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, PasswordResetForm, SetPasswordForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


User = get_user_model()


def _append_css_class(widget, css_class: str):
    existing = widget.attrs.get("class", "").strip()
    classes = f"{existing} {css_class}".strip() if existing else css_class
    widget.attrs["class"] = classes


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


class UserRegistrationForm(forms.ModelForm):
    full_name = forms.CharField(
        label="Full Name",
        max_length=160,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Enter your full name",
                "autocomplete": "name",
            }
        ),
    )
    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Create a strong password",
                "autocomplete": "new-password",
            }
        ),
        help_text=_("Use at least 8 characters with a mix of letters, numbers, and symbols."),
    )
    password2 = forms.CharField(
        label="Confirm Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Confirm your password",
                "autocomplete": "new-password",
            }
        ),
    )
    phone_number = forms.CharField(
        label="Phone Number",
        required=False,
        max_length=64,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Optional",
                "autocomplete": "tel",
            }
        ),
    )
    organization = forms.CharField(
        label="Organization / Company",
        required=False,
        max_length=120,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Optional",
                "autocomplete": "organization",
            }
        ),
    )
    job_title = forms.CharField(
        label="Job Title / Designation",
        required=False,
        max_length=120,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Optional",
                "autocomplete": "organization-title",
            }
        ),
    )
    profile_notes = forms.CharField(
        label="Profile Notes",
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Optional notes",
            }
        ),
    )

    class Meta:
        model = User
        fields = ("username", "email")
        widgets = {
            "username": forms.TextInput(
                attrs={
                    "placeholder": "Choose a username",
                    "autocomplete": "username",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "placeholder": "name@company.com",
                    "autocomplete": "email",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            _append_css_class(field.widget, "auth-input")

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if not username:
            raise ValidationError("Username is required.")
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("This username is already in use.")
        return username

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise ValidationError("Email is required.")
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("This email is already in use.")
        return email

    def clean_password1(self):
        return self.cleaned_data.get("password1")

    def clean(self):
        cleaned_data = super().clean()
        username = (cleaned_data.get("username") or "").strip()
        email = (cleaned_data.get("email") or "").strip().lower()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1:
            candidate_user = User(username=username, email=email)
            try:
                validate_password(password1, candidate_user)
            except ValidationError as exc:
                self.add_error("password1", exc)

        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Passwords do not match.")
        return cleaned_data


class StyledPasswordResetForm(PasswordResetForm):
    email = forms.EmailField(
        label="Email Address",
        max_length=254,
        widget=forms.EmailInput(
            attrs={
                "placeholder": "Enter your account email",
                "autocomplete": "email",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _append_css_class(self.fields["email"].widget, "auth-input")


class StyledSetPasswordForm(SetPasswordForm):
    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        self.fields["new_password1"].label = "New Password"
        self.fields["new_password2"].label = "Confirm New Password"
        self.fields["new_password1"].widget.attrs.update(
            {"placeholder": "New password", "autocomplete": "new-password"}
        )
        self.fields["new_password2"].widget.attrs.update(
            {"placeholder": "Confirm new password", "autocomplete": "new-password"}
        )
        _append_css_class(self.fields["new_password1"].widget, "auth-input")
        _append_css_class(self.fields["new_password2"].widget, "auth-input")


class StyledPasswordChangeForm(PasswordChangeForm):
    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        self.fields["old_password"].label = "Current Password"
        self.fields["new_password1"].label = "New Password"
        self.fields["new_password2"].label = "Confirm New Password"
        self.fields["old_password"].widget.attrs.update(
            {"placeholder": "Current password", "autocomplete": "current-password"}
        )
        self.fields["new_password1"].widget.attrs.update(
            {"placeholder": "New password", "autocomplete": "new-password"}
        )
        self.fields["new_password2"].widget.attrs.update(
            {"placeholder": "Confirm new password", "autocomplete": "new-password"}
        )
        _append_css_class(self.fields["old_password"].widget, "auth-input")
        _append_css_class(self.fields["new_password1"].widget, "auth-input")
        _append_css_class(self.fields["new_password2"].widget, "auth-input")
