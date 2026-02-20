from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from billing_service.services.invoice_service import InvoiceService

router = APIRouter(prefix="/invoices")


async def _get_db(request: Request) -> AsyncSession:
    async with request.app.state.db_pool() as session:
        yield session


def _tenant_id_from_header(request: Request) -> uuid.UUID:
    tid = request.headers.get("x-tenant-id")
    if not tid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="x-tenant-id header required")
    return uuid.UUID(tid)


@router.get("")
async def list_invoices(
    request: Request,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(_get_db),
) -> dict[str, Any]:
    tenant_id = _tenant_id_from_header(request)
    svc = InvoiceService(db)
    invoices = await svc.list_invoices(tenant_id, limit=limit, offset=offset)
    return {"invoices": invoices, "count": len(invoices)}


@router.get("/{invoice_id}")
async def get_invoice(
    invoice_id: str,
    request: Request,
    db: AsyncSession = Depends(_get_db),
) -> dict[str, Any]:
    tenant_id = _tenant_id_from_header(request)
    svc = InvoiceService(db)
    invoice = await svc.get_invoice(tenant_id, uuid.UUID(invoice_id))
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return invoice


@router.get("/{invoice_id}/pdf")
async def get_invoice_pdf(
    invoice_id: str,
    request: Request,
    db: AsyncSession = Depends(_get_db),
) -> RedirectResponse:
    tenant_id = _tenant_id_from_header(request)
    svc = InvoiceService(db)
    invoice = await svc.get_invoice(tenant_id, uuid.UUID(invoice_id))
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    if not invoice.get("pdf_url"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF not available")
    return RedirectResponse(url=invoice["pdf_url"], status_code=status.HTTP_302_FOUND)
