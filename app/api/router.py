from fastapi import APIRouter

from app.api.routes import ui, workflow


api_router = APIRouter()

api_router.include_router(ui.router, tags=["ui"])
api_router.include_router(workflow.router, prefix="/api", tags=["workflow"])

