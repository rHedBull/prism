from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from billing_service.models.invoice import Invoice
from billing_service.models.subscription import Subscription


class InvoiceService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_invoices(
        self, tenant_id: uuid.UUID, limit: int = 20, offset: int = 0
    ) -> list[dict[str, Any]]:
        result = await self._db.execute(
            select(Invoice)
            .where(Invoice.tenant_id == tenant_id)
            .order_by(Invoice.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        invoices = result.scalars().all()
        return [
            {
                "id": str(inv.id),
                "stripe_invoice_id": inv.stripe_invoice_id,
                "amount_cents": inv.amount_cents,
                "currency": inv.currency,
                "status": inv.status,
                "paid_at": inv.paid_at.isoformat() if inv.paid_at else None,
                "pdf_url": inv.pdf_url,
                "created_at": inv.created_at.isoformat(),
            }
            for inv in invoices
        ]

    async def get_invoice(
        self, tenant_id: uuid.UUID, invoice_id: uuid.UUID
    ) -> dict[str, Any] | None:
        result = await self._db.execute(
            select(Invoice).where(
                Invoice.id == invoice_id,
                Invoice.tenant_id == tenant_id,
            )
        )
        inv = result.scalar_one_or_none()
        if inv is None:
            return None
        return {
            "id": str(inv.id),
            "stripe_invoice_id": inv.stripe_invoice_id,
            "amount_cents": inv.amount_cents,
            "currency": inv.currency,
            "status": inv.status,
            "paid_at": inv.paid_at.isoformat() if inv.paid_at else None,
            "pdf_url": inv.pdf_url,
            "description": inv.description,
            "created_at": inv.created_at.isoformat(),
        }

    async def sync_from_stripe(self, tenant_id: uuid.UUID) -> int:
        sub_result = await self._db.execute(
            select(Subscription).where(Subscription.tenant_id == tenant_id)
        )
        subscription = sub_result.scalar_one_or_none()
        if subscription is None:
            raise ValueError("No subscription found for tenant")

        stripe_invoices = stripe.Invoice.list(
            customer=subscription.stripe_customer_id, limit=100
        )

        synced = 0
        for si in stripe_invoices.auto_paging_iter():
            existing = await self._db.execute(
                select(Invoice).where(Invoice.stripe_invoice_id == si.id)
            )
            invoice = existing.scalar_one_or_none()

            paid_at = (
                datetime.fromtimestamp(si.status_transitions.paid_at, tz=timezone.utc)
                if si.status_transitions and si.status_transitions.paid_at
                else None
            )

            if invoice is None:
                invoice = Invoice(
                    tenant_id=tenant_id,
                    stripe_invoice_id=si.id,
                    amount_cents=si.amount_paid or 0,
                    currency=si.currency or "usd",
                    status=si.status or "draft",
                    paid_at=paid_at,
                    pdf_url=si.invoice_pdf,
                    description=si.description,
                )
                self._db.add(invoice)
                synced += 1
            else:
                invoice.status = si.status or invoice.status
                invoice.amount_cents = si.amount_paid or invoice.amount_cents
                invoice.paid_at = paid_at or invoice.paid_at
                invoice.pdf_url = si.invoice_pdf or invoice.pdf_url

        await self._db.commit()
        return synced
