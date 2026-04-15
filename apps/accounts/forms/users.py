from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.password_validation import validate_password

User = get_user_model()


class UserLoginForm(forms.Form):
    username = forms.CharField(max_length=32, label="Username")
    password = forms.CharField(widget=forms.PasswordInput, label="Password")

    def clean(self):
        data = self.cleaned_data
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        user = authenticate(self.request, username=username, password=password)

        if user is None:
            raise forms.ValidationError("Invalid credentials.")

        if not user.is_active:
            raise forms.ValidationError("Your account is inactive. Please activate your account via the activation email.")

        # Store the user in the form so we can access it later in the view
        self.user = user
        return data

    def __init__(self, request, *args, **kwargs):
        self.request = request
        super(UserLoginForm, self).__init__(*args, **kwargs)


class CustomPasswordChangeForm(PasswordChangeForm):
    new_password1 = forms.CharField(widget=forms.PasswordInput, label="Password", validators=[validate_password])

    class Meta:
        model = User
        fields = (
            'old_password',
            'new_password1',
            'new_password2'
        )


class UserRegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, label="Password")
    confirm_password = forms.CharField(widget=forms.PasswordInput, label="Confirm Password")

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'password']

    def clean_password(self):
        password = self.cleaned_data.get('password')
        try:
            validate_password(password)
        except ValidationError as e:
            raise ValidationError("Password must be at least 8 characters long, not be too common, and cannot be entirely numeric.")
        return password

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get("username")
        email = cleaned_data.get("email")
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        # Check if passwords match
        if password and confirm_password and password != confirm_password:
            raise ValidationError("Passwords don't match!")

        # Check for duplicate username
        if User.objects.filter(username=username).exists():
            raise ValidationError("Username already exists.")

        # Check for duplicate email
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email address already exists.")
        return cleaned_data


class ForgetPasswordForm(forms.Form):
    email = forms.EmailField(label='Email', max_length=32)


class PasswordResetForm(forms.Form):
    new_password = forms.CharField(
        widget=forms.PasswordInput,
        label="New Password",
        validators=[validate_password],
        max_length=128
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput,
        label="Confirm New Password",
        max_length=128
    )

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get("new_password")
        confirm_password = cleaned_data.get("confirm_password")

        if new_password and confirm_password:
            if new_password != confirm_password:
                raise forms.ValidationError("The two password fields didn't match.")
        return cleaned_data


class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError("A user with this email already exists.")
        return email


class OTPForm(forms.Form):
    otp = forms.CharField(max_length=6, label="Enter OTP", widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Enter the OTP sent to your email'
    }))
