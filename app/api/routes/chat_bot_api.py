from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field

from app.services.chat_bot_service import ChatBotService

logger = logging.getLogger(__name__)

router = APIRouter()

service = ChatBotService()

# Only one polling loop in-process (для UI-локальной отладки).
polling_task: asyncio.Task[None] | None = None
polling_task_lock = asyncio.Lock()


class WebhookSubscriptionCreateRequest(BaseModel):
    callback_url: str = Field(..., description="Публичный URL, куда HH отправит callback")


class WebhookSubscriptionCancelRequest(BaseModel):
    subscription_id: str


class ChatCreateRequest(BaseModel):
    resume_url_or_hash: str = Field(..., description="URL вида https://hh.ru/resume/<hash> или сам hash")
    first_message: str = Field(..., description="Сообщение работодателя в чат-старте (нужно HH для создания/получения чата)")
    system_prompt: str | None = None
    user_prompt_template: str | None = None
    target_text: str | None = None
    auto_reply_enabled: bool = True
    polling_enabled: bool = True
    polling_interval_sec: int = Field(30, ge=5, le=600)


class ChatSendRequest(BaseModel):
    chat_id: str | None = None
    resume_url_or_hash: str | None = None
    text: str = Field(..., description="Текст сообщения")
    # If chat_id is not provided, we will only work with configured state after create_or_get_chat.


class PollerStartRequest(BaseModel):
    resume_url_or_hash: str | None = None
    chat_id: str | None = None
    interval_sec: int = Field(30, ge=5, le=600)


class PollerStopRequest(BaseModel):
    resume_url_or_hash: str | None = None


@router.post("/webhook/subscription/create")
def webhook_subscription_create(req: WebhookSubscriptionCreateRequest) -> dict[str, Any]:
    # Register only one action: CHAT_MESSAGE_CREATED.
    sub = service.hh.post_webhook_subscription(url=req.callback_url, action_types=["CHAT_MESSAGE_CREATED"])
    return {"ok": True, "subscription": sub}


@router.get("/webhook/subscription/list")
def webhook_subscription_list() -> dict[str, Any]:
    subs = service.hh.get_webhook_subscriptions()
    return {"ok": True, "subscriptions": subs}


@router.post("/webhook/subscription/cancel")
def webhook_subscription_cancel(req: WebhookSubscriptionCancelRequest) -> dict[str, Any]:
    service.hh.cancel_webhook_subscription(subscription_id=req.subscription_id)
    return {"ok": True}


@router.post("/chat/create", response_model=dict)
def chat_create(req: ChatCreateRequest) -> dict[str, Any]:
    return service.create_or_get_chat(
        resume_url_or_hash=req.resume_url_or_hash,
        first_message=req.first_message,
        system_prompt=req.system_prompt,
        user_prompt_template=req.user_prompt_template,
        target_text=req.target_text,
        auto_reply_enabled=req.auto_reply_enabled,
        polling_enabled=req.polling_enabled,
        polling_interval_sec=req.polling_interval_sec,
    )


@router.post("/chat/send", response_model=dict)
def chat_send(req: ChatSendRequest) -> dict[str, Any]:
    if req.chat_id:
        return {"ok": True, "sent": service.send_text(chat_id=req.chat_id, text=req.text)}

    if req.resume_url_or_hash:
        # Resolve configured chat_id from store by resume_hash.
        resume_hash = service.parse_resume_hash(req.resume_url_or_hash)
        state = service.store.get_state_by_resume_hash(resume_hash=resume_hash)
        chat_id = state.get("chat_id") if state else None
        if not chat_id:
            return {"ok": False, "error": "chat_id_not_configured", "resume_hash": resume_hash}
        return {"ok": True, "sent": service.send_text(chat_id=str(chat_id), text=req.text)}

    return {"ok": False, "error": "chat_id_or_resume_url_or_hash_required"}


async def _poller_loop() -> None:
    """
    Background loop:
    - periodically calls poll_once()
    - poll_once() internally filters by configured enabled chats
    """
    logger.info("Chat bot poller loop started")
    try:
        while True:
            await asyncio.sleep(1)
            # Run poll once for all enabled states.
            await asyncio.to_thread(service.poll_once)

            # Respect the minimum interval among enabled states.
            enabled = service.store.get_polling_enabled_states()
            if not enabled:
                logger.info("Chat bot poller loop stopped (no enabled states)")
                return
            min_interval = min(int(st.get("polling_interval_sec") or 30) for st in enabled)
            # Sleep for that interval.
            await asyncio.sleep(max(5, min_interval))
    except asyncio.CancelledError:
        logger.info("Chat bot poller loop cancelled")
        return
    except Exception:
        logger.exception("Chat bot poller loop failed")
        return


@router.post("/poller/start")
async def poller_start(req: PollerStartRequest, bg: BackgroundTasks) -> dict[str, Any]:
    # Update store flags if user provided interval + resume.
    if req.resume_url_or_hash:
        resume_hash = service.parse_resume_hash(req.resume_url_or_hash)
        service.store.set_polling_flags(
            resume_hash=resume_hash,
            polling_enabled=True,
            polling_interval_sec=req.interval_sec,
        )
    elif req.chat_id:
        # We don't have reverse mapping chat_id->resume_hash update helper;
        # simplest path: just set polling flags by chat_id if exists.
        state = service.store.get_state_by_chat_id(chat_id=req.chat_id)
        if state and state.get("resume_hash"):
            service.store.set_polling_flags(
                resume_hash=str(state["resume_hash"]),
                polling_enabled=True,
                polling_interval_sec=req.interval_sec,
            )

    async with polling_task_lock:
        global polling_task
        if polling_task and not polling_task.done():
            return {"ok": True, "already_running": True}
        polling_task = asyncio.create_task(_poller_loop())

    # Fire-and-forget; loop will call poll_once immediately in next iterations.
    return {"ok": True, "already_running": False}


@router.post("/poller/stop")
async def poller_stop(req: PollerStopRequest) -> dict[str, Any]:
    if req.resume_url_or_hash:
        resume_hash = service.parse_resume_hash(req.resume_url_or_hash)
        service.store.set_polling_flags(resume_hash=resume_hash, polling_enabled=False, polling_interval_sec=None)

    async with polling_task_lock:
        global polling_task
        if polling_task and not polling_task.done():
            polling_task.cancel()
            polling_task = None
    return {"ok": True}


@router.post("/poller/once")
async def poller_once() -> dict[str, Any]:
    res = await asyncio.to_thread(service.poll_once)
    return {"ok": True, "result": res}


@router.get("/state")
def bot_state(resume_url_or_hash: str | None = None, chat_id: str | None = None) -> dict[str, Any]:
    if resume_url_or_hash:
        resume_hash = service.parse_resume_hash(resume_url_or_hash)
        st = service.store.get_state_by_resume_hash(resume_hash=resume_hash)
        return {"ok": True, "state": st}
    if chat_id:
        st = service.store.get_state_by_chat_id(chat_id=chat_id)
        return {"ok": True, "state": st}
    return {"ok": False, "error": "resume_url_or_hash_or_chat_id_required"}


@router.get("/events")
def bot_events(limit: int = 30) -> dict[str, Any]:
    events = service.store.list_recent_events(limit=limit)
    return {"ok": True, "events": events}


@router.post("/webhook")
async def webhook(payload: dict[str, Any]) -> dict[str, Any]:
    """
    HH callback handler for CHAT_MESSAGE_CREATED.
    HH sends: { action_type, id, subscription_id, user_id, payload: { chat_id, message_id, ... } }
    """
    try:
        action_type = payload.get("action_type")
        data = payload.get("payload") or {}
        chat_id = data.get("chat_id")
        message_id = data.get("message_id")

        if action_type != "CHAT_MESSAGE_CREATED" or not chat_id or not message_id:
            return {"ok": True, "ignored": True, "reason": "unexpected_payload"}

        # Run heavy work in background.
        async def _work() -> None:
            try:
                await asyncio.to_thread(
                    service.handle_new_message_created,
                    chat_id=str(chat_id),
                    message_id=str(message_id),
                    source="webhook",
                )
            except Exception:
                logger.exception("webhook handler failed")

        asyncio.create_task(_work())
        return {"ok": True}
    except Exception:
        logger.exception("webhook parsing failed")
        return {"ok": True}

