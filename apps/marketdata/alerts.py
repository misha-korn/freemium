"""Price-alert evaluation — Stage 5.

When a fresh quote is stored, ``check_price_alerts`` fires any of the asset's
active alerts whose threshold the new price has crossed: it notifies the owner
(in-app + their chosen channels) and deactivates the alert so it fires once.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING

from django.utils import timezone
from django.utils.translation import gettext as _

from .models import PriceAlert

if TYPE_CHECKING:
    from apps.portfolio.models import Asset

logger = logging.getLogger(__name__)


def check_price_alerts(asset: Asset, price: Decimal) -> int:
    """Fire crossed alerts for ``asset`` at ``price``; return how many triggered."""
    from apps.notifications.services import notify_user

    alerts = PriceAlert.objects.filter(asset=asset, is_active=True).select_related("user")
    triggered = 0
    for alert in alerts:
        crossed = (
            alert.direction == PriceAlert.Direction.ABOVE and price >= alert.threshold
        ) or (
            alert.direction == PriceAlert.Direction.BELOW and price <= alert.threshold
        )
        if not crossed:
            continue

        arrow = "≥" if alert.direction == PriceAlert.Direction.ABOVE else "≤"
        notify_user(
            alert.user,
            kind="PRICE_ALERT",
            title=_("Price alert: %(ticker)s") % {"ticker": asset.ticker},
            body=_("%(ticker)s is now %(price)s (target %(arrow)s %(threshold)s).")
            % {
                "ticker": asset.ticker,
                "price": price,
                "arrow": arrow,
                "threshold": alert.threshold,
            },
        )
        alert.is_active = False
        alert.triggered_at = timezone.now()
        alert.save(update_fields=["is_active", "triggered_at"])
        triggered += 1

    if triggered:
        logger.info("Triggered %s price alert(s) for %s", triggered, asset.ticker)
    return triggered
