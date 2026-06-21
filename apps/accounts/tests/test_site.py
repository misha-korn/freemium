"""The data migration brands the default Site (used in allauth emails)."""
import pytest
from django.conf import settings
from django.contrib.sites.models import Site


@pytest.mark.django_db
def test_default_site_is_branded():
    site = Site.objects.get(pk=settings.SITE_ID)
    assert site.name == "Freemium"
    assert site.domain == "freemium-web-02ef.onrender.com"
