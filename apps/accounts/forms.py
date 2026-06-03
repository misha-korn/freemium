"""Account forms."""
from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()


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
