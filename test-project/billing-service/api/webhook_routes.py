from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from billing_service.integrations.stripe_client import StripeClient
from billing_service.models.invoice import Invoice
from billing_service.models.subscription import Subscription, SubscriptionStatus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks")


@router.post("/stripe")
async def stripe_webhook(request: Request) -> dict[str, str]:
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = StripeClient.construct_webhook_event(payload, sig_header)
    except Exception as exc:
        logger.warning("Webhook signature verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook signature",
        )

    async with request.app.state.db_pool() as db:
        await _handle_event(db, event)

    return {"status": "ok"}


async def _handle_event(db: AsyncSession, event: dict) -> None:
    event_type = event["type"]
    data = event["data"]["object"]

    handlers = {
        "invoice.paid": _handle_invoice_paid,
        "subscription.updated": _handle_subscription_updated,
        "subscription.deleted": _handle_subscription_deleted,
        "payment_intent.failed": _handle_payment_failed,
    }

    handler = handlers.get(event_type)
    if handler is None:
        logger.debug("Unhandled webhook event type: %s", event_type)
        return

    await handler(db, data)


async def _handle_invoice_paid(db: AsyncSession, data: dict) -> None:
    stripe_invoice_id = data["id"]
    customer_id = data["customer"]

    result = await db.execute(
        select(Subscription).where(Subscription.stripe_customer_id == customer_id)
    )
    subscription = result.scalar_one_or_none()
    if subscription is None:
        logger.warning("No subscription found for customer %s", customer_id)
        return

    existing = await db.execute(
        select(Invoice).where(Invoice.stripe_invoice_id == stripe_invoice_id)
    )
    invoice = existing.scalar_one_or_none()

    paid_at = datetime.now(timezone.utc)
    if invoice is None:
        invoice = Invoice(
            tenant_id=subscription.tenant_id,
            stripe_invoice_id=stripe_invoice_id,
            amount_cents=data.get("amount_paid", 0),
            currency=data.get("currency", "usd"),
            status="paid",
            paid_at=paid_at,
            pdf_url=data.get("invoice_pdf"),
        )
        db.add(invoice)
    else:
        invoice.status = "paid"
        invoice.paid_at = paid_at
        invoice.pdf_url = data.get("invoice_pdf", invoice.pdf_url)

    await db.commit()
    logger.info("Invoice %s marked as paid for tenant %s", stripe_invoice_id, subscription.tenant_id)


async def _handle_subscription_updated(db: AsyncSession, data: dict) -> None:
    stripe_sub_id = data["id"]
    result = await db.execute(
        select(Subscription).where(
            Subscription.stripe_subscription_id == stripe_sub_id
        )
    )
    subscription = result.scalar_one_or_none()
    if subscription is None:
        logger.warning("No subscription found for stripe_subscription_id %s", stripe_sub_id)
        return

    new_status = data.get("status")
    if new_status:
        try:
            subscription.status = SubscriptionStatus(new_status)
        except ValueError:
            logger.warning("Unknown subscription status: %s", new_status)

    if data.get("current_period_start"):
        subscription.current_period_start = datetime.fromtimestamp(
            data["current_period_start"], tz=timezone.utc
        )
    if data.get("current_period_end"):
        subscription.current_period_end = datetime.fromtimestamp(
            data["current_period_end"], tz=timezone.utc
        )

    cancel_at = data.get("cancel_at")
    subscription.cancel_at = (
        datetime.fromtimestamp(cancel_at, tz=timezone.utc) if cancel_at else None
    )

    await db.commit()
    logger.info("Subscription %s updated to status %s", stripe_sub_id, new_status)


async def _handle_subscription_deleted(db: AsyncSession, data: dict) -> None:
    stripe_sub_id = data["id"]
    result = await db.execute(
        select(Subscription).where(
            Subscription.stripe_subscription_id == stripe_sub_id
        )
    )
    subscription = result.scalar_one_or_none()
    if subscription is None:
        return

    subscription.status = SubscriptionStatus.CANCELED
    await db.commit()
    logger.info("Subscription %s canceled", stripe_sub_id)


async def _handle_payment_failed(db: AsyncSession, data: dict) -> None:
    customer_id = data.get("customer")
    if not customer_id:
        return

    result = await db.execute(
        select(Subscription).where(Subscription.stripe_customer_id == customer_id)
    )
    subscription = result.scalar_one_or_none()
    if subscription is None:
        return

    subscription.status = SubscriptionStatus.PAST_DUE
    await db.commit()
    logger.warning(
        "Payment failed for tenant %s — subscription marked as past_due",
        subscription.tenant_id,
    )
