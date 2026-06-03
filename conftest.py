"""Shared pytest fixtures."""
import pytest
from django.contrib.auth import get_user_model


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(
        username="alice", email="alice@example.com", password="pw-12345!"
    )


@pytest.fixture
def other_user(db):
    return get_user_model().objects.create_user(
        username="bob", email="bob@example.com", password="pw-12345!"
    )


@pytest.fixture
def auth_client(client, user):
    client.force_login(user)
    return client
