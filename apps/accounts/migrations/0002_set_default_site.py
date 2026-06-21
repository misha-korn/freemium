"""Replace Django's default example.com Site with the project's brand + domain.

allauth's emails (verification, password reset) greet with ``Site.name`` and
reference ``Site.domain``. The framework ships an "example.com" placeholder,
which showed up in the confirmation email. Point the Site at the live brand and
deployment host. Change later via Django admin → Sites (or a custom domain).
"""
from django.conf import settings
from django.db import migrations

SITE_DOMAIN = "freemium-web-02ef.onrender.com"
SITE_NAME = "Freemium"


def set_site(apps, schema_editor):
    Site = apps.get_model("sites", "Site")
    Site.objects.update_or_create(
        pk=getattr(settings, "SITE_ID", 1),
        defaults={"domain": SITE_DOMAIN, "name": SITE_NAME},
    )


def revert_site(apps, schema_editor):
    Site = apps.get_model("sites", "Site")
    Site.objects.filter(pk=getattr(settings, "SITE_ID", 1)).update(
        domain="example.com", name="example.com"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("sites", "0002_alter_domain_unique"),
    ]

    operations = [migrations.RunPython(set_site, revert_site)]
