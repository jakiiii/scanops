from django import forms
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.contrib.auth import get_user_model

User = get_user_model()


class UserAdminCreationForm(forms.ModelForm):
    password1 = forms.CharField(max_length=32, label='password', widget=forms.PasswordInput)
    password2 = forms.CharField(max_length=32, label='Password Confirmation', widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = (
            'username',
        )

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Password have to match")
        return password2

    def save(self, commit=True):
        user = super(UserAdminCreationForm, self).save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class UserAdminChangeForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField(label="Password", help_text=("Raw passwords are not stored, so there is no way to see " "this user's password, but you can change the password " "using <a href=\"../password/\">this form</a>."))

    class Meta:
        model = User
        fields = (
            'first_name',
            'last_name',
            'username',
            'password',
            'is_active',
            'is_staff',
            'is_superuser',
            'is_administrator',
            'is_operator',
        )

    def clean_password(self):
        return self.initial["password"]
