from __future__ import annotations

import logging
from typing import Any

import stripe

from billing_service.config.settings import settings

logger = logging.getLogger(__name__)

stripe.api_key = settings.stripe_secret_key
stripe.api_version = settings.stripe_api_version


class StripeClient:
    async def create_customer(
        self, email: str, name: str, tenant_id: str, metadata: dict[str, str] | None = None
    ) -> stripe.Customer:
        meta = {"tenant_id": tenant_id}
        if metadata:
            meta.update(metadata)
        customer = stripe.Customer.create(
            email=email,
            name=name,
            metadata=meta,
        )
        logger.info("Created Stripe customer %s for tenant %s", customer.id, tenant_id)
        return customer

    async def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        trial_days: int | None = None,
    ) -> stripe.Subscription:
        params: dict[str, Any] = {
            "customer": customer_id,
            "items": [{"price": price_id}],
            "payment_behavior": "default_incomplete",
            "expand": ["latest_invoice.payment_intent"],
        }
        if trial_days:
            params["trial_period_days"] = trial_days
        subscription = stripe.Subscription.create(**params)
        logger.info("Created Stripe subscription %s", subscription.id)
        return subscription

    async def update_subscription(
        self, subscription_id: str, new_price_id: str
    ) -> stripe.Subscription:
        subscription = stripe.Subscription.retrieve(subscription_id)
        updated = stripe.Subscription.modify(
            subscription_id,
            items=[
                {
                    "id": subscription["items"]["data"][0]["id"],
                    "price": new_price_id,
                }
            ],
            proration_behavior="create_prorations",
        )
        logger.info("Updated subscription %s to price %s", subscription_id, new_price_id)
        return updated

    async def cancel_subscription(
        self, subscription_id: str, at_period_end: bool = True
    ) -> stripe.Subscription:
        if at_period_end:
            sub = stripe.Subscription.modify(
                subscription_id, cancel_at_period_end=True
            )
        else:
            sub = stripe.Subscription.delete(subscription_id)
        logger.info("Canceled subscription %s (at_period_end=%s)", subscription_id, at_period_end)
        return sub

    async def create_checkout_session(
        self,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
    ) -> stripe.checkout.Session:
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return session

    @staticmethod
    def construct_webhook_event(
        payload: bytes, sig_header: str
    ) -> stripe.Event:
        return stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
