from fastapi import APIRouter

from app.api.routes import chat_bot_api, chat_bot_ui, ui, workflow


api_router = APIRouter()

api_router.include_router(ui.router, tags=["ui"])
api_router.include_router(chat_bot_ui.router, tags=["chat_bot_ui"])
api_router.include_router(workflow.router, prefix="/api", tags=["workflow"])
api_router.include_router(chat_bot_api.router, prefix="/api/chat_bot", tags=["chat_bot"])

