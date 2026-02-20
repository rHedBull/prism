from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from billing_service.integrations.stripe_client import StripeClient
from billing_service.services.subscription_service import SubscriptionService

router = APIRouter(prefix="/subscription")


class CreateSubscriptionRequest(BaseModel):
    tenant_id: str
    email: EmailStr
    name: str
    plan_id: str
    price_id: str
    trial_days: int | None = 14


class UpdatePlanRequest(BaseModel):
    new_plan_id: str
    new_price_id: str


class CancelRequest(BaseModel):
    immediate: bool = False


async def _get_db(request: Request) -> AsyncSession:
    async with request.app.state.db_pool() as session:
        yield session


def _get_stripe_client() -> StripeClient:
    return StripeClient()


async def _get_subscription_service(
    db: AsyncSession = Depends(_get_db),
    stripe_client: StripeClient = Depends(_get_stripe_client),
) -> SubscriptionService:
    return SubscriptionService(db, stripe_client)


def _tenant_id_from_header(request: Request) -> uuid.UUID:
    tid = request.headers.get("x-tenant-id")
    if not tid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="x-tenant-id header required")
    try:
        return uuid.UUID(tid)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant ID")


@router.get("")
async def get_subscription(
    request: Request,
    svc: SubscriptionService = Depends(_get_subscription_service),
) -> dict[str, Any]:
    tenant_id = _tenant_id_from_header(request)
    sub = await svc.get_subscription(tenant_id)
    if sub is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No subscription found")
    return {
        "id": str(sub.id),
        "tenant_id": str(sub.tenant_id),
        "plan_id": sub.plan_id,
        "status": sub.status.value,
        "current_period_start": sub.current_period_start.isoformat() if sub.current_period_start else None,
        "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
        "cancel_at": sub.cancel_at.isoformat() if sub.cancel_at else None,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_subscription(
    body: CreateSubscriptionRequest,
    svc: SubscriptionService = Depends(_get_subscription_service),
) -> dict[str, Any]:
    try:
        result = await svc.create_subscription(
            tenant_id=uuid.UUID(body.tenant_id),
            email=body.email,
            name=body.name,
            plan_id=body.plan_id,
            price_id=body.price_id,
            trial_days=body.trial_days,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return result


@router.patch("/plan")
async def update_plan(
    body: UpdatePlanRequest,
    request: Request,
    svc: SubscriptionService = Depends(_get_subscription_service),
) -> dict[str, Any]:
    tenant_id = _tenant_id_from_header(request)
    try:
        sub = await svc.update_plan(tenant_id, body.new_plan_id, body.new_price_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {
        "id": str(sub.id),
        "plan_id": sub.plan_id,
        "status": sub.status.value,
    }


@router.delete("", status_code=status.HTTP_200_OK)
async def cancel_subscription(
    body: CancelRequest,
    request: Request,
    svc: SubscriptionService = Depends(_get_subscription_service),
) -> dict[str, Any]:
    tenant_id = _tenant_id_from_header(request)
    try:
        sub = await svc.cancel_subscription(tenant_id, immediate=body.immediate)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {
        "id": str(sub.id),
        "status": sub.status.value,
        "cancel_at": sub.cancel_at.isoformat() if sub.cancel_at else None,
    }
