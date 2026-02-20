from fastapi import APIRouter

from auth_service.api.auth_routes import router as auth_router
from auth_service.api.oauth_routes import router as oauth_router
from auth_service.api.user_routes import router as user_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router, tags=["auth"])
api_router.include_router(user_router, tags=["users"])
api_router.include_router(oauth_router, tags=["oauth"])
