from fastapi import APIRouter

from billing_service.api.invoice_routes import router as invoice_router
from billing_service.api.subscription_routes import router as subscription_router
from billing_service.api.webhook_routes import router as webhook_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(subscription_router, tags=["subscriptions"])
api_router.include_router(invoice_router, tags=["invoices"])
api_router.include_router(webhook_router, tags=["webhooks"])
