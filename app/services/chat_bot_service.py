from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.clients.hh_chat_client import HHChatClient
from app.clients.llm_client import LLMClient
from app.core.chat_bot_store import SqliteChatBotStore, get_chat_bot_store
from app.core.settings import settings

logger = logging.getLogger(__name__)


class ChatBotService:
    def __init__(self, *, hh_client: HHChatClient | None = None, store: SqliteChatBotStore | None = None) -> None:
        self.hh = hh_client or HHChatClient()
        self.store = store or get_chat_bot_store()
        self.llm = LLMClient(llm_url=settings.llm_url, token_param=settings.llm_token_param)

    @staticmethod
    def parse_resume_hash(resume_url_or_hash: str) -> str:
        s = (resume_url_or_hash or "").strip()
        if not s:
            raise ValueError("resume_url_or_hash is empty")

        # Accept direct hash.
        if "/resume/" not in s:
            return s

        # Examples:
        # https://hh.ru/resume/<hash>?hhtmFrom=resume_list
        m = re.search(r"/resume/([^/?#]+)", s)
        if not m:
            raise ValueError("Unable to extract resume_hash from URL")
        return m.group(1)

    @staticmethod
    def _pick_text_from_message_text_payload(payload: dict[str, Any] | None) -> str:
        if not isinstance(payload, dict):
            return ""
        txt = payload.get("text")
        if isinstance(txt, str):
            return txt.strip()
        return ""

    @staticmethod
    def _coerce_reply_text(llm_raw: Any) -> str:
        if not llm_raw:
            return ""

        if isinstance(llm_raw, str):
            return llm_raw.strip()

        if isinstance(llm_raw, dict):
            response = llm_raw.get("response", llm_raw)
            if isinstance(response, str):
                return response.strip()
            if isinstance(response, dict):
                for key in ("reply_text", "text", "message", "answer", "markdown"):
                    val = response.get(key)
                    if isinstance(val, str) and val.strip():
                        # If model returns markdown inside, still acceptable as plain text.
                        return val.strip()
                    if isinstance(val, dict):
                        # Sometimes markdown is returned as { "markdown": "..." }.
                        md = val.get("markdown")
                        if isinstance(md, str) and md.strip():
                            return md.strip()
                # Last resort: try JSON stringify.
                try:
                    return str(response).strip()
                except Exception:
                    return ""

        # Unknown shape.
        return str(llm_raw).strip()

    def create_or_get_chat(
        self,
        *,
        resume_url_or_hash: str,
        first_message: str,
        system_prompt: str | None,
        user_prompt_template: str | None,
        target_text: str | None,
        auto_reply_enabled: bool,
        polling_enabled: bool,
        polling_interval_sec: int,
    ) -> dict[str, Any]:
        resume_hash = self.parse_resume_hash(resume_url_or_hash)

        # Always update prompts/state even if chat lookup fails.
        self.store.upsert_state(
            resume_hash=resume_hash,
            chat_id=None,
            auto_reply_enabled=auto_reply_enabled,
            polling_enabled=polling_enabled,
            polling_interval_sec=polling_interval_sec,
            system_prompt=system_prompt,
            user_prompt_template=user_prompt_template,
            target_text=target_text,
        )

        # Try to create (or fetch) the chat. Response schema in openapi is empty,
        # so we'll likely need to resolve chat_id from the chat list.
        resp = self.hh.get_or_create_chat_without_vacancy_common(resume_hash=resume_hash, first_message=first_message)

        # If HH actually returns chat_id, use it.
        chat_id = None
        if isinstance(resp, dict):
            for k in ("chat_id", "id"):
                val = resp.get(k)
                if isinstance(val, str) and val.strip():
                    chat_id = val.strip()

        if not chat_id:
            chat_id = self._resolve_chat_id_by_last_message(resume_hash=resume_hash, first_message=first_message)

        if chat_id:
            self.store.upsert_state(
                resume_hash=resume_hash,
                chat_id=chat_id,
                auto_reply_enabled=auto_reply_enabled,
                polling_enabled=polling_enabled,
                polling_interval_sec=polling_interval_sec,
                system_prompt=system_prompt,
                user_prompt_template=user_prompt_template,
                target_text=target_text,
            )

        return {"resume_hash": resume_hash, "chat_id": chat_id, "raw_create_response": resp}

    def _resolve_chat_id_by_last_message(self, *, resume_hash: str, first_message: str) -> str | None:
        """
        Основная идея: в payload списка чатов нет `resume_hash`, поэтому мы ищем чат по `first_message`.

        Сценарий "чат уже существовал": тогда последний message может НЕ быть равен `first_message`,
        поэтому есть fallback — пробуем найти `first_message` в истории последних сообщений чата.
        """
        target = (first_message or "").strip()
        if not target:
            return None

        # We need some time for HH to index the chat.
        deadline = datetime.now(timezone.utc).timestamp() + 20
        first_loop = True

        while datetime.now(timezone.utc).timestamp() < deadline:
            try:
                chats = self.hh.get_common_chat_list(page=0, per_page=20)
                items = chats.get("items") or []

                # 1) Fast path: exact match on last_message.text.
                for it in items:
                    try:
                        last_msg = it.get("last_message") or {}
                        payload = last_msg.get("payload") or {}
                        last_text = self._pick_text_from_message_text_payload(payload)
                        if last_text and last_text.strip() == target:
                            cid = it.get("id")
                            if isinstance(cid, str) and cid.strip():
                                return cid.strip()
                    except Exception:
                        continue

                # 2) Fallback (выполняем один раз): чат существует, но последний message другой.
                if first_loop:
                    first_loop = False
                    # limit HH requests: scanning too many chats can be slow/rate-limited
                    candidate_ids: list[str] = []
                    for it in items:
                        cid = it.get("id")
                        if isinstance(cid, str) and cid.strip():
                            candidate_ids.append(cid.strip())
                        if len(candidate_ids) >= 10:
                            break

                    for chat_id in candidate_ids:
                        try:
                            history_resp = self.hh.get_chat_messages(
                                chat_id=chat_id,
                                limit=20,
                                order="prev",
                            )
                            history_list = history_resp.get("messages") if isinstance(history_resp, dict) else None
                            if not isinstance(history_list, list):
                                continue
                            for mi in history_list:
                                p = mi.get("payload") or {}
                                txt = self._pick_text_from_message_text_payload(p)
                                if txt and txt.strip() == target:
                                    return chat_id
                        except Exception:
                            continue
            except Exception:
                logger.exception("resolve_chat_id_by_last_message failed (resume_hash=%s)", resume_hash)

            time.sleep(1)

        logger.warning("Unable to resolve chat_id for resume_hash=%s", resume_hash)
        return None

    def send_text(self, *, chat_id: str, text: str) -> dict[str, Any]:
        if not text.strip():
            raise ValueError("Cannot send empty message")
        idempotency_key = str(uuid4())
        return self.hh.chat_message_post(chat_id=chat_id, text=text, idempotency_key=idempotency_key)

    def _build_reply_prompt(
        self,
        *,
        system_prompt: str | None,
        user_prompt_template: str | None,
        target_text: str | None,
        last_message_text: str,
        conversation: list[dict[str, str]],
    ) -> str:
        # conversation: list of {"role": "...", "text": "..."}.
        history = "\n".join([f"{m['role']}: {m['text']}" for m in conversation if m.get("text")])

        system = system_prompt or "Ты ассистент рекрутера на hh.ru."
        if user_prompt_template and "{last_message}" in user_prompt_template:
            user_t = user_prompt_template
        else:
            user_t = (
                "Требования/позиция:\n{target_text}\n\n"
                "История переписки (последние сообщения):\n{history}\n\n"
                "Последнее сообщение кандидата:\n{last_message}\n\n"
                "Сформируй ответ работодателя. Верни только текст ответа без JSON."
            )

        return (
            f"{system}\n\n"
            + user_t.format(
                target_text=target_text or "",
                history=history,
                last_message=last_message_text,
            )
        )

    def _sender_role_label(self, raw_role: str | None) -> str:
        if raw_role == "APPLICANT":
            return "Кандидат"
        if raw_role == "EMPLOYER":
            return "Работодатель"
        if raw_role == "BOT":
            return "Бот"
        return raw_role or "Участник"

    def handle_new_message_created(self, *, chat_id: str, message_id: str, source: str) -> dict[str, Any]:
        state = self.store.get_state_by_chat_id(chat_id=chat_id)
        if not state:
            # Safety: ignore unknown chats.
            return {"ignored": True, "reason": "unknown_chat_id", "chat_id": chat_id}

        if not state.get("auto_reply_enabled"):
            return {"ignored": True, "reason": "auto_reply_disabled", "chat_id": chat_id}

        last_processed = state.get("last_processed_message_id")
        if last_processed and str(last_processed) == str(message_id):
            return {"ignored": True, "reason": "already_processed", "chat_id": chat_id}

        # Fetch the message itself (to get text + sender role).
        msg_resp = self.hh.get_chat_messages(chat_id=chat_id, start_message_id=message_id, limit=1, order="next")
        # openapi: ChatsCommonMessagesResponse -> messages is a list
        msg_list = msg_resp.get("messages") if isinstance(msg_resp, dict) else None
        if not isinstance(msg_list, list) or not msg_list:
            return {"ok": False, "error": "message_not_found", "chat_id": chat_id, "message_id": message_id}

        m0 = msg_list[0]
        payload = m0.get("payload") or {}
        incoming_text = self._pick_text_from_message_text_payload(payload)
        sender_role_raw = None
        sender_display = m0.get("sender_display_info") or {}
        if isinstance(sender_display, dict):
            sender_role_raw = sender_display.get("role")

        # Safety: only auto-reply on candidate messages.
        if sender_role_raw != "APPLICANT":
            # Update last_processed anyway to reduce repeated triggers from our own messages.
            self.store.update_last_processed(resume_hash=state["resume_hash"], message_id=str(message_id))
            return {
                "ignored": True,
                "reason": "not_applicant_message",
                "chat_id": chat_id,
                "sender_role": sender_role_raw,
            }

        system_prompt = state.get("system_prompt")
        user_prompt_template = state.get("user_prompt_template")
        target_text = state.get("target_text")

        # Load history for better reply quality.
        history_resp = self.hh.get_chat_messages(chat_id=chat_id, limit=12, order="prev")
        history_list = history_resp.get("messages") if isinstance(history_resp, dict) else None
        if not isinstance(history_list, list):
            history_list = []

        conversation: list[dict[str, str]] = []
        for mi in history_list:
            try:
                p = mi.get("payload") or {}
                txt = self._pick_text_from_message_text_payload(p)
                if not txt:
                    continue
                sd = mi.get("sender_display_info") or {}
                role_raw = sd.get("role")
                conversation.append({"role": self._sender_role_label(role_raw), "text": txt})
            except Exception:
                continue

        prompt = self._build_reply_prompt(
            system_prompt=system_prompt,
            user_prompt_template=user_prompt_template,
            target_text=target_text,
            last_message_text=incoming_text,
            conversation=conversation[-8:],
        )

        llm_raw = self.llm.call(prompt_text=prompt, iteration=0)
        reply_text = self._coerce_reply_text(llm_raw)

        ok = False
        error = None
        try:
            if not reply_text:
                raise ValueError("LLM returned empty reply")
            self.send_text(chat_id=chat_id, text=reply_text)
            ok = True
        except Exception as e:
            error = str(e)
            logger.exception("failed to send bot reply")

        self.store.add_event(
            resume_hash=state["resume_hash"],
            chat_id=chat_id,
            message_id=str(message_id),
            source=source,
            incoming_text=incoming_text,
            reply_text=reply_text,
            ok=ok,
            error=error,
        )

        if ok:
            self.store.update_last_processed(resume_hash=state["resume_hash"], message_id=str(message_id))

        return {"ok": ok, "chat_id": chat_id, "message_id": message_id, "reply_text": reply_text, "error": error}

    def poll_once(self) -> dict[str, Any]:
        """
        Poller: checks unread count and processes only configured chats.
        """
        enabled_states = self.store.get_polling_enabled_states()
        if not enabled_states:
            return {"ok": True, "processed": 0, "reason": "polling_disabled"}

        processed = 0
        latest_scan = self.hh.get_common_chat_list(filter_unread=True, per_page=20, page=0)
        items = latest_scan.get("items") or []

        for st in enabled_states:
            chat_id = st.get("chat_id")
            if not chat_id or not isinstance(chat_id, str):
                continue

            chat_item = next((it for it in items if str(it.get("id")) == chat_id), None)
            if not chat_item:
                continue

            unread = int(chat_item.get("unread_message_count") or 0)
            if unread <= 0:
                continue

            # Load last message.
            history_resp = self.hh.get_chat_messages(chat_id=chat_id, limit=1, order="prev")
            history_list = history_resp.get("messages") if isinstance(history_resp, dict) else None
            if not isinstance(history_list, list):
                history_list = []
            if not history_list:
                continue

            last_m = history_list[0]
            last_message_id = last_m.get("id")
            if not last_message_id:
                continue

            state = self.store.get_state_by_chat_id(chat_id=chat_id)
            if not state:
                continue

            if state.get("last_processed_message_id") and str(state["last_processed_message_id"]) == str(last_message_id):
                continue

            res = self.handle_new_message_created(chat_id=str(chat_id), message_id=str(last_message_id), source="poll")
            processed += 1 if res.get("ok") else 0

        return {"ok": True, "processed": processed}

