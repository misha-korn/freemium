"""Account-area routes (mounted under /u/).

allauth owns the auth flows (login, signup, logout, password reset) under
/accounts/. This namespace holds our own profile/subscription pages.
"""
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("profile/edit/", views.ProfileUpdateView.as_view(), name="profile_edit"),
    path("subscription/", views.SubscriptionView.as_view(), name="subscription"),
]
