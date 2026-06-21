"""Account forms."""
from __future__ import annotations

from allauth.account.forms import LoginForm as AllauthLoginForm
from allauth.account.forms import SignupForm as AllauthSignupForm
from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class LoginForm(AllauthLoginForm):
    """allauth login form with a clearer credential label.

    allauth labels the credential field "Login", which in Russian renders as
    "Войти" — identical to the page heading and the submit button, so the page
    showed "Войти" three times. Relabel it.
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        if "login" in self.fields:
            self.fields["login"].label = _("Username or email")


class SignupForm(AllauthSignupForm):
    """allauth signup form without the always-on password-rule list.

    Django lists every password rule as help text between the two password
    fields. Drop it so the rules appear only as errors when actually violated.
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        if "password1" in self.fields:
            self.fields["password1"].help_text = ""


class ProfileForm(forms.ModelForm):
    """Edit the logged-in user's basic profile fields."""

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]

    def clean_email(self) -> str:
        email: str = self.cleaned_data["email"]
        qs = User.objects.filter(email__iexact=email)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("This email address is already in use.")
        return email
