from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/ui/bot", response_class=HTMLResponse)
def bot_ui() -> str:
    return """
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>HH Bot Automator</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }

    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      background: #ffffff;
      color: #000000;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }

    .container {
      width: 100%;
      max-width: 1100px;
      position: relative;
      border: 1px solid #000000;
      background: #ffffff;
    }

    .corner { position: absolute; width: 30px; height: 30px; border-style: solid; border-color: #000000; }
    .corner-tl { top: 30px; left: 30px; border-width: 3px 0 0 3px; }
    .corner-tr { top: 30px; right: 30px; border-width: 3px 3px 0 0; }
    .corner-bl { bottom: 30px; left: 30px; border-width: 0 0 3px 3px; }
    .corner-br { bottom: 30px; right: 30px; border-width: 0 3px 3px 0; }

    .content { padding: 60px 35px; display: flex; flex-direction: column; gap: 22px; }

    .title {
      font-size: 3.2rem;
      font-weight: 600;
      letter-spacing: -2px;
      line-height: 1.05;
    }
    .subtitle { font-size: 14px; letter-spacing: 3px; text-transform: uppercase; color: #666666; }

    textarea {
      width: 100%;
      min-height: 180px;
      padding: 18px 18px;
      border: 2px solid #000000;
      font-size: 20px;
      line-height: 1.35;
      outline: none;
      resize: vertical;
      border-radius: 0;
      background: #ffffff;
    }
    input:not([type="checkbox"]) {
      padding: 14px 18px;
      border: 2px solid #000000;
      font-size: 16px;
      line-height: 1.35;
      outline: none;
      resize: none;
      border-radius: 0;
      background: #ffffff;
    }

    .section {
      border: 1px solid #000000;
      padding: 14px 14px;
      background: #fff;
    }
    .section h2 {
      font-size: 12px;
      letter-spacing: 3px;
      text-transform: uppercase;
      color: #666666;
      margin-bottom: 8px;
      font-weight: 600;
    }

    label { display:flex; flex-direction: column; gap: 6px; margin: 10px 0; }

    /* Вся разметка на странице должна быть сверху-вниз (без "двух колонок"). */
    .row { display:flex; flex-direction: column; gap: 12px; align-items: stretch; }
    .grow { flex: 1; min-width: 280px; }

    button {
      border: 2px solid #000;
      background: #000;
      color: #fff;
      padding: 14px 18px;
      font-size: 16px;
      letter-spacing: 1px;
      text-transform: uppercase;
      cursor: pointer;
      font-weight: 700;
      border-radius: 0;
    }
    button.primary { background: #000; color: #fff; }
    button.secondary { background: #fff; color: #000; }
    button:disabled { opacity: 0.5; cursor: not-allowed; }

    .hint { font-size: 12px; color:#666666; margin-top: 6px; letter-spacing: 2px; text-transform: uppercase; }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; }
    .status { font-size: 14px; margin-top: 2px; }

    .list { width:100%; border:1px solid #000; overflow:hidden; }
    table { width:100%; border-collapse: collapse; }
    th, td { border: 1px solid #000000; padding: 10px 10px; vertical-align: top; }
    th { text-transform: uppercase; letter-spacing: 2px; font-size: 12px; background: #000; color: #fff; }
    td { font-size: 15px; }

    /* Табличные кнопки должны быть компактными, как на основном экране. */
    .list button {
      padding: 8px 10px;
      font-size: 12px;
      letter-spacing: 0;
      text-transform: none;
      line-height: 1;
    }

    .danger { color:#b00020; font-weight: 800; }

    @media (max-width: 900px) {
      .title { font-size: 2.4rem; }
      textarea { font-size: 18px; min-height: 140px; }
      .content { padding: 40px 18px; }
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="corner corner-tl"></div>
    <div class="corner corner-tr"></div>
    <div class="corner corner-bl"></div>
    <div class="corner corner-br"></div>

    <div class="content">
      <div class="subtitle">UI бота</div>
      <div class="title">HH Чат</div>

      <div style="text-align: right; margin-top: -10px;">
        <button id="btnBack" class="secondary" type="button" title="Вернуться на главный экран">
          ← Назад на главный экран
        </button>
      </div>

      <div class="section">
        <h2>1) Webhook подписка</h2>
        <div class="row">
          <div class="grow">
            <div class="hint">Callback endpoint</div>
            <input id="callbackUrl" class="mono" readonly />
          </div>
          <div style="min-width: 250px;">
            <div class="hint">Действие: только <span class="mono">CHAT_MESSAGE_CREATED</span></div>
            <button id="btnCreateSub" class="primary">Создать подписку</button>
          </div>
        </div>
        <div class="row" style="margin-top: 8px;">
          <button id="btnListSubs" class="secondary">Обновить список</button>
        </div>
        <div style="margin-top: 10px;" class="list">
          <table>
            <thead>
              <tr>
                <th>subscription_id</th>
                <th>actions</th>
                <th>url</th>
                <th>cancel</th>
              </tr>
            </thead>
            <tbody id="subsTbody"></tbody>
          </table>
        </div>
      </div>

      <div class="section">
        <h2>2) Чат по резюме</h2>
        <div class="row">
          <label class="grow">
            resume_url_or_hash
            <input id="resumeInput" placeholder="https://hh.ru/resume/&lt;hash&gt; или просто hash" />
          </label>
          <div class="row" style="margin-top: 10px;">
            <label class="grow">
              chat_id:
              <input id="chatIdBox" class="mono" readonly placeholder="после создания" />
            </label>
          </div>
          <label class="grow">
            first_message (то, что HH отправит в чат при создании)
            <textarea id="firstMessageInput">Здравствуйте! Заинтересовало ваше резюме. Хотим обсудить детали. Удобно?</textarea>
          </label>
        </div>
        <div class="row">
          <div style="flex-direction: row; gap: 10px; justify-content: center; display: flex;">
            <button id="btnCreateChat" class="primary">Создать/получить чат</button>
            <button id="btnLoadState" class="secondary">Загрузить state</button>
          </div>
        </div>
        <div class="status" id="chatStatus"></div>
      </div>

      <div class="section">
        <h2>3) Автоответчик</h2>
        <div class="row">
          <label style="min-width: 320px;">
            system_prompt
            <textarea id="systemPromptInput">Ты ассистент рекрутера. Пиши вежливо по-русски. Ответ должен быть кратким и полезным.</textarea>
          </label>
          <label class="grow">
            user_prompt_template
            <textarea id="userPromptTemplateInput">Требования/позиция:\n{target_text}\n\nИстория переписки (последние сообщения):\n{history}\n\nПоследнее сообщение кандидата:\n{last_message}\n\nСформируй ответ работодателя. Верни только текст ответа без JSON.</textarea>
          </label>
        </div>
        <div class="row">
          <label style="min-width: 360px;">
            target_text (что учитывать в ответе)
            <textarea id="targetTextInput">Позиция: ...\nКлючевые требования: ...</textarea>
          </label>
        </div>
        <div class="row">
          <label style="margin: 0; padding: 6px 0; display: flex; flex-direction: row; justify-content: center;">
            <input type="checkbox" id="autoReplyEnabled" checked />
            auto_reply_enabled
          </label>
          <label style="margin: 0; padding: 6px 0; display: flex; flex-direction: row; justify-content: center;">
            <input type="checkbox" id="pollingEnabled" checked />
            polling_enabled (fallback к webhook)
          </label>
          <label style="min-width: 260px;">
            polling_interval_sec
            <input id="intervalInput" type="number" value="30" min="5" max="600" />
          </label>
        </div>
        <div class="row">
          <div style="flex-direction: row; gap: 10px; justify-content: center; display: flex;">
            <button id="btnPollOnce" class="secondary">Poll once</button>
            <button id="btnStartPolling" class="primary">Старт polling</button>
            <button id="btnStopPolling" class="secondary">Стоп polling</button>
          </div>
        </div>
      </div>

      <div class="section">
        <h2>4) Ручная отправка</h2>
        <div class="row">
          <label class="grow">
            text
            <textarea id="manualTextInput">Можете коротко рассказать про ваш опыт и ближайшие планы?</textarea>
          </label>
        </div>
        <div class="row">
          <button id="btnSendManual" class="primary">Написать</button>
        </div>
        <div class="status" id="manualStatus"></div>
      </div>

      <div class="section">
        <h2>5) Лог</h2>
        <div class="row">
          <button id="btnRefreshEvents" class="secondary">Обновить события</button>
        </div>
        <div class="list">
          <table>
            <thead>
              <tr>
                <th>created_at</th>
                <th>resume_hash</th>
                <th>chat_id</th>
                <th>message_id</th>
                <th>source</th>
                <th>ok</th>
                <th>error</th>
              </tr>
            </thead>
            <tbody id="eventsTbody"></tbody>
          </table>
        </div>
      </div>

    </div>
  </div>

<script>
  const el = (id) => document.getElementById(id);
  const qs = (k) => new URLSearchParams(window.location.search).get(k);

  let state = {
    resumeUrlOrHash: "",
    chatId: "",
  };

  function setStatus(targetEl, text) {
    if (!targetEl) return;
    targetEl.textContent = text || "";
  }

  function extractChatStateFromResponse(resp) {
    if (!resp || !resp.state) return null;
    return resp.state;
  }

  async function postJson(path, body) {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const t = await res.text();
    let data = null;
    try { data = t ? JSON.parse(t) : null; } catch(e) {}
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${t || "no body"}`);
    }
    return data;
  }

  async function getJson(path) {
    const res = await fetch(path);
    const t = await res.text();
    let data = null;
    try { data = t ? JSON.parse(t) : null; } catch(e) {}
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${t || "no body"}`);
    }
    return data;
  }

  async function refreshSubs() {
    const data = await getJson("/api/chat_bot/webhook/subscription/list");
    const subs = data.subscriptions || [];
    const tbody = el("subsTbody");
    tbody.innerHTML = "";
    subs.forEach((s) => {
      const tr = document.createElement("tr");
      const actions = Array.isArray(s.actions) ? s.actions.map(a => a.type).join(", ") : "";
      tr.innerHTML = `
        <td class="mono">${escapeHtml(String(s.subscription_id ?? ""))}</td>
        <td class="mono">${escapeHtml(String(actions || ""))}</td>
        <td class="mono">${escapeHtml(String(s.url ?? ""))}</td>
        <td><button class="secondary" data-subid="${escapeAttr(String(s.subscription_id ?? ""))}">Отменить</button></td>
      `;
      tbody.appendChild(tr);
    });

    Array.from(tbody.querySelectorAll("button[data-subid]")).forEach((b) => {
      b.onclick = async (e) => {
        e.preventDefault();
        const subId = b.getAttribute("data-subid");
        if (!subId) return;
        if (!confirm("Отменить подписку " + subId + "?")) return;
        await postJson("/api/chat_bot/webhook/subscription/cancel", { subscription_id: subId });
        await refreshSubs();
      };
    });
  }

  async function refreshEvents() {
    const data = await getJson("/api/chat_bot/events?limit=30");
    const events = data.events || [];
    const tbody = el("eventsTbody");
    tbody.innerHTML = "";
    events.forEach((ev) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="mono">${escapeHtml(String(ev.created_at ?? ""))}</td>
        <td class="mono">${escapeHtml(String(ev.resume_hash ?? ""))}</td>
        <td class="mono">${escapeHtml(String(ev.chat_id ?? ""))}</td>
        <td class="mono">${escapeHtml(String(ev.message_id ?? ""))}</td>
        <td class="mono">${escapeHtml(String(ev.source ?? ""))}</td>
        <td class="mono">${escapeHtml(String(ev.ok ?? ""))}</td>
        <td>${escapeHtml(String(ev.error ?? ""))}</td>
      `;
      tbody.appendChild(tr);
    });
  }

  function escapeHtml(s) {
    return String(s)
      .replaceAll("&","&amp;")
      .replaceAll("<","&lt;")
      .replaceAll(">","&gt;")
      .replaceAll('"',"&quot;")
      .replaceAll("'","&#039;");
  }
  function escapeAttr(s) { return escapeHtml(s).replaceAll("\\n"," "); }

  async function createChat() {
    const resume = el("resumeInput").value.trim();
    const firstMsg = el("firstMessageInput").value;
    if (!resume) throw new Error("Укажите resume_url_or_hash");
    setStatus(el("chatStatus"), "Создаю чат...");
    const sys = el("systemPromptInput").value;
    const userT = el("userPromptTemplateInput").value;
    const target = el("targetTextInput").value;
    const autoEnabled = !!el("autoReplyEnabled").checked;
    const pollingEnabled = !!el("pollingEnabled").checked;
    const intervalSec = Number(el("intervalInput").value || 30);

    const resp = await postJson("/api/chat_bot/chat/create", {
      resume_url_or_hash: resume,
      first_message: firstMsg,
      system_prompt: sys,
      user_prompt_template: userT,
      target_text: target,
      auto_reply_enabled: autoEnabled,
      polling_enabled: pollingEnabled,
      polling_interval_sec: intervalSec
    });
    const chatId = resp.chat_id ? String(resp.chat_id) : "";
    el("chatIdBox").value = chatId;
    state.resumeUrlOrHash = resume;
    state.chatId = chatId;
    if (chatId) {
      setStatus(el("chatStatus"), `Готово. chat_id=${chatId}; смотрите state в "Загрузить state"`);
    } else {
      setStatus(
        el("chatStatus"),
        "Создан/получен запрос на чат, но chat_id пока пустой. " +
        "Это значит, что backend не смог определить chat_id по вашему first_message. " +
        "Попробуйте: (1) сделайте first_message короче/уникальнее, (2) нажмите «Создать/получить чат» ещё раз."
      );
    }
  }

  async function loadState() {
    const resume = el("resumeInput").value.trim();
    if (!resume) throw new Error("Укажите resume_url_or_hash");
    const data = await getJson("/api/chat_bot/state?resume_url_or_hash=" + encodeURIComponent(resume));
    if (!data.ok) {
      setStatus(el("chatStatus"), "state: " + (data.error || "unknown error"));
      return false;
    }
    const st = data.state || {};
    el("chatIdBox").value = st.chat_id ? String(st.chat_id) : "";
    el("intervalInput").value = st.polling_interval_sec ? String(st.polling_interval_sec) : String(el("intervalInput").value);
    if (typeof st.auto_reply_enabled !== "undefined") el("autoReplyEnabled").checked = !!st.auto_reply_enabled;
    if (typeof st.polling_enabled !== "undefined") el("pollingEnabled").checked = !!st.polling_enabled;
    setStatus(el("chatStatus"), "state загружен");
    return Boolean(st.chat_id);
  }

  async function startPolling() {
    const resume = el("resumeInput").value.trim();
    if (!resume) throw new Error("Укажите resume_url_or_hash");
    const intervalSec = Number(el("intervalInput").value || 30);
    await postJson("/api/chat_bot/poller/start", { resume_url_or_hash: resume, interval_sec: intervalSec });
    setStatus(el("chatStatus"), "poller старт/обновлён");
  }

  async function stopPolling() {
    const resume = el("resumeInput").value.trim();
    if (!resume) throw new Error("Укажите resume_url_or_hash");
    await postJson("/api/chat_bot/poller/stop", { resume_url_or_hash: resume });
    setStatus(el("chatStatus"), "poller остановлен (local)");
  }

  async function pollOnce() {
    await postJson("/api/chat_bot/poller/once", {});
    setStatus(el("chatStatus"), "poll_once выполнен");
    await refreshEvents();
  }

  async function sendManual() {
    try {
      const text = el("manualTextInput").value;
      const chatId = el("chatIdBox").value.trim();
      const resume = el("resumeInput").value.trim();
      if (!text.trim()) throw new Error("Введите text");
      let body = { text: text };
      if (chatId) body.chat_id = chatId; else if (resume) body.resume_url_or_hash = resume;
      else throw new Error("Нужен chat_id или resume_url_or_hash");

      const resp = await postJson("/api/chat_bot/chat/send", body);
      if (resp?.ok) {
        setStatus(el("manualStatus"), "send: ok");
        await refreshEvents();
        return;
      }

      if (resp?.error === "chat_id_not_configured") {
        setStatus(
          el("manualStatus"),
          "Не могу отправить: chat_id не настроен для этого resume. " +
          "Сначала нажмите «Создать/получить чат» (шаг 2), дождитесь появления chat_id, затем повторите."
        );
        return;
      }

      setStatus(el("manualStatus"), "send error: " + JSON.stringify(resp));
    } catch (e) {
      setStatus(el("manualStatus"), "Ошибка отправки: " + (e?.message || String(e)));
    }
  }

  async function createSubscription() {
    const callbackUrl = el("callbackUrl").value.trim();
    await postJson("/api/chat_bot/webhook/subscription/create", { callback_url: callbackUrl });
    await refreshSubs();
  }

  async function init() {
    const origin = window.location.origin;
    el("callbackUrl").value = origin + "/api/chat_bot/webhook";

    const resumeFromQuery = qs("resume_url") || qs("resume_hash") || "";
    if (resumeFromQuery) {
      el("resumeInput").value = resumeFromQuery;
      state.resumeUrlOrHash = resumeFromQuery;
      // If chat_id is not configured yet, automatically try to create/resolve it.
      try {
        const hasChat = await loadState();
        if (!hasChat) {
          setStatus(el("chatStatus"), "chat_id не найден в state — пробую «Создать/получить чат»...");
          await createChat();
          await refreshEvents();
        }
      } catch(e) {}
    }

    el("btnCreateSub").onclick = async () => { setStatus(el("chatStatus"), "Создаю подписку..."); await createSubscription(); setStatus(el("chatStatus"), "Подписка создана/обновлена"); };
    el("btnListSubs").onclick = async () => refreshSubs();
    el("btnCreateChat").onclick = async () => { await createChat(); await refreshEvents(); };
    el("btnLoadState").onclick = async () => { await loadState(); await refreshEvents(); };
    el("btnStartPolling").onclick = async () => { await startPolling(); await refreshEvents(); };
    el("btnStopPolling").onclick = async () => { await stopPolling(); await refreshEvents(); };
    el("btnPollOnce").onclick = async () => { await pollOnce(); };
    el("btnSendManual").onclick = async () => { await sendManual(); };
    el("btnRefreshEvents").onclick = async () => { await refreshEvents(); };
    el("btnBack").onclick = () => { window.location.href = "/"; };

    // initial loads
    try { await refreshSubs(); } catch(e) {}
    try { await refreshEvents(); } catch(e) {}
  }

  init().catch((e) => {
    setStatus(el("chatStatus"), "Ошибка инициализации: " + (e?.message || String(e)));
  });
</script>
</body>
</html>
    """

