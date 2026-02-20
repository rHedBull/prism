from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from billing_service.integrations.stripe_client import StripeClient
from billing_service.models.subscription import Subscription, SubscriptionStatus


class SubscriptionService:
    def __init__(self, db: AsyncSession, stripe_client: StripeClient) -> None:
        self._db = db
        self._stripe = stripe_client

    async def get_subscription(self, tenant_id: uuid.UUID) -> Subscription | None:
        result = await self._db.execute(
            select(Subscription).where(Subscription.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def create_subscription(
        self,
        tenant_id: uuid.UUID,
        email: str,
        name: str,
        plan_id: str,
        price_id: str,
        trial_days: int | None = 14,
    ) -> dict[str, Any]:
        existing = await self.get_subscription(tenant_id)
        if existing is not None:
            raise ValueError("Tenant already has an active subscription")

        customer = await self._stripe.create_customer(
            email=email, name=name, tenant_id=str(tenant_id)
        )
        stripe_sub = await self._stripe.create_subscription(
            customer_id=customer.id,
            price_id=price_id,
            trial_days=trial_days,
        )

        subscription = Subscription(
            tenant_id=tenant_id,
            plan_id=plan_id,
            stripe_customer_id=customer.id,
            stripe_subscription_id=stripe_sub.id,
            status=SubscriptionStatus(stripe_sub.status),
            current_period_start=datetime.fromtimestamp(
                stripe_sub.current_period_start, tz=timezone.utc
            ),
            current_period_end=datetime.fromtimestamp(
                stripe_sub.current_period_end, tz=timezone.utc
            ),
        )
        self._db.add(subscription)
        await self._db.commit()
        await self._db.refresh(subscription)

        client_secret = None
        latest_invoice = stripe_sub.get("latest_invoice")
        if latest_invoice and isinstance(latest_invoice, dict):
            pi = latest_invoice.get("payment_intent")
            if pi and isinstance(pi, dict):
                client_secret = pi.get("client_secret")

        return {
            "subscription_id": str(subscription.id),
            "stripe_subscription_id": stripe_sub.id,
            "status": subscription.status.value,
            "client_secret": client_secret,
        }

    async def update_plan(
        self, tenant_id: uuid.UUID, new_plan_id: str, new_price_id: str
    ) -> Subscription:
        subscription = await self.get_subscription(tenant_id)
        if subscription is None:
            raise ValueError("No subscription found for tenant")

        if subscription.status not in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING):
            raise ValueError(f"Cannot update plan — subscription is {subscription.status.value}")

        await self._stripe.update_subscription(
            subscription.stripe_subscription_id, new_price_id
        )
        subscription.plan_id = new_plan_id
        await self._db.commit()
        await self._db.refresh(subscription)
        return subscription

    async def cancel_subscription(
        self, tenant_id: uuid.UUID, immediate: bool = False
    ) -> Subscription:
        subscription = await self.get_subscription(tenant_id)
        if subscription is None:
            raise ValueError("No subscription found for tenant")

        stripe_sub = await self._stripe.cancel_subscription(
            subscription.stripe_subscription_id, at_period_end=not immediate
        )

        if immediate:
            subscription.status = SubscriptionStatus.CANCELED
        else:
            subscription.cancel_at = datetime.fromtimestamp(
                stripe_sub.cancel_at, tz=timezone.utc
            ) if stripe_sub.cancel_at else subscription.current_period_end

        await self._db.commit()
        await self._db.refresh(subscription)
        return subscription

    async def check_usage_limits(self, tenant_id: uuid.UUID) -> dict[str, Any]:
        from billing_service.services.usage_service import UsageService
        subscription = await self.get_subscription(tenant_id)
        if subscription is None:
            return {"allowed": False, "reason": "No active subscription"}

        usage_svc = UsageService(self._db)
        summary = await usage_svc.get_usage_summary(tenant_id)
        quota = self._get_quota_for_plan(subscription.plan_id)

        total_used = sum(m["total"] for m in summary.values())
        if quota != -1 and total_used >= quota:
            return {
                "allowed": False,
                "reason": "Usage quota exceeded",
                "used": total_used,
                "quota": quota,
            }
        return {"allowed": True, "used": total_used, "quota": quota}

    @staticmethod
    def _get_quota_for_plan(plan_id: str) -> int:
        from billing_service.config.settings import settings
        quotas = {
            "free": settings.usage_quota_free,
            "starter": settings.usage_quota_starter,
            "pro": settings.usage_quota_pro,
            "enterprise": settings.usage_quota_enterprise,
        }
        return quotas.get(plan_id, settings.usage_quota_free)
