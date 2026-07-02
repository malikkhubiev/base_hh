import logging

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.core.tracing import trace_step

router = APIRouter()
_log = logging.getLogger(__name__)


@router.get("/", response_class=HTMLResponse)
def index() -> str:
    # Встроенный single-file UI для локальной отладки пайплайна.
    trace_step(_log, "ui", "index")
    return """
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>HH Optimizer</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      background: #ffffff; color: #000000;
      min-height: 100vh;
      display: flex; align-items: center; justify-content: center;
      padding: 20px;
    }
    .container {
      width: 100%; max-width: 1100px;
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
      font-size: 3.2rem; font-weight: 600;
      letter-spacing: -2px; line-height: 1.05;
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
    }

    .row { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
    button {
      border: 2px solid #000;
      background: #000;
      color: #fff;
      padding: 14px 18px;
      font-size: 16px;
      letter-spacing: 1px;
      text-transform: uppercase;
      cursor: pointer;
    }
    button.secondary { background: #fff; color: #000; }
    button:disabled { opacity: 0.5; cursor: not-allowed; }

    .pill {
      border: 1px solid #000;
      padding: 10px 12px;
      font-size: 13px;
      letter-spacing: 1px;
      text-transform: uppercase;
      background: #fff;
    }
    .pill input { margin-right: 8px; }

    .grid3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
    .stack { display: flex; flex-direction: column; gap: 12px; }
    .card {
      border: 1px solid #000;
      padding: 14px 14px;
      background: #fff;
    }
    .card .label {
      font-size: 12px;
      letter-spacing: 3px;
      text-transform: uppercase;
      color: #666666;
      margin-bottom: 8px;
    }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; }
    .big { font-size: 18px; line-height: 1.25; word-break: break-word; }
    .link-preview {
      display: block;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      margin-bottom: 10px;
      font-size: 13px;
    }

    .divider { border-top: 1px solid #000; margin: 10px 0; }

    .llm {
      border: 1px solid #000;
      padding: 14px;
      background: #f5f5f5;
    }
    .prompt-editor { min-height: 120px; font-size: 14px; }
    .param-block {
      margin-top: 10px;
      border-top: 1px dashed #000;
      padding-top: 10px;
      display: none;
    }
    .param-group { margin-bottom: 10px; }
    .param-title { font-size: 12px; text-transform: uppercase; letter-spacing: 2px; color: #666; }
    .param-item { font-size: 14px; margin-top: 4px; }

    table { width: 100%; border-collapse: collapse; }
    th, td { border: 1px solid #000; padding: 10px 10px; vertical-align: top; }
    th { text-transform: uppercase; letter-spacing: 2px; font-size: 12px; background: #000; color: #fff; }
    td { font-size: 15px; }
    a { color: #000; }

    .cell-actions-td { padding: 0 !important; }
    .cell-actions {
      display: flex;
      width: 100%;
      height: 100%;
      min-height: 44px;
    }
    .cell-actions button {
      flex: 1 1 0;
      width: 100%;
      height: 100%;
      border: 0;
      border-left: 1px solid #000;
      padding: 10px 8px;
      font-size: 12px;
      text-transform: none;
      letter-spacing: 0;
      line-height: 1.1;
      cursor: pointer;
    }
    .cell-actions button:first-child { border-left: 0; }
    .cell-actions button.secondary { background: #fff; color: #000; }
    .cell-actions a {
      flex: 1 1 0;
      width: 100%;
      height: 100%;
      border: 0;
      border-left: 1px solid #000;
      padding: 10px 8px;
      font-size: 12px;
      text-transform: none;
      letter-spacing: 0;
      line-height: 1.1;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      text-decoration: none;
      background: #fff;
      color: #000;
    }
    .cell-actions a:first-child { border-left: 0; }
    .cell-actions a.disabled {
      opacity: 0.5;
      cursor: not-allowed;
      pointer-events: none;
    }

    .level-tab {
      border: 2px solid #000;
      background: #fff;
      color: #000;
      padding: 10px 12px;
      font-size: 13px;
      letter-spacing: 1px;
      text-transform: uppercase;
      cursor: pointer;
    }
    .level-tab.active {
      background: #000;
      color: #fff;
    }

    .tl-rect {
      min-width: 56px;
      height: 30px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border: 1px solid #000;
      font-weight: 700;
      cursor: pointer;
      user-select: none;
      padding: 0 8px;
    }

    .tl-modal-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,.35);
      display: none;
      align-items: center;
      justify-content: center;
      padding: 20px;
      z-index: 9999;
    }
    .tl-modal {
      width: 100%;
      max-width: 1200px;
      background: #fff;
      border: 1px solid #888;
      padding: 14px;
      max-height: 85vh;
      overflow: auto;
    }

    .tl-modal table th, .tl-modal table td {
      border-color: #666 !important;
    }

    @media (max-width: 900px) {
      .grid3 { grid-template-columns: 1fr; }
      .title { font-size: 2.4rem; }
      textarea { font-size: 18px; }
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
      <div>
        <div class="subtitle">отладка workflow</div>
        <div class="title">Поиск резюме (LLM → булевы → HH → просмотр)</div>
      </div>

      <textarea id="requestText" placeholder="Вставьте запрос/требования..."></textarea>

      <div class="row">
        <div class="stack" style="flex:2; min-width:260px;">
          <div class="row">
            <button class="secondary" id="btnDefault">Запрос по умолчанию</button>
            <button class="secondary" id="btnBool">Далее</button>
            <button id="btnSearch">Поиск</button>
          </div>
        </div>
        <div class="stack" style="flex:3; min-width:260px;">
          <div class="row">
            <label class="pill">
              Количество кандидатов
              <input type="number" id="candLimit" value="10" min="1" max="200" />
            </label>
            <label class="pill">
              <input type="checkbox" id="area113" checked />
              Россия (113)
            </label>
            <label class="pill">
              <input type="checkbox" id="area16" checked />
              Беларусь (16)
            </label>
          </div>
        </div>
      </div>

      <div id="status" class="subtitle"></div>
      <div id="progressStage" class="subtitle" style="color:#333;"></div>
      <div id="progressTimes" class="subtitle" style="color:#333;"></div>
      <!-- debug blocks removed by task -->

      <div id="queries" class="grid3" style="display:none;"></div>
      <div id="queryLinks" class="stack" style="display:none;"></div>

      <div id="results" style="display:none;">
        <div class="divider"></div>
        <div class="subtitle" id="pickedInfo"></div>
        <div id="finalQueryInfo" class="card" style="margin-top:10px; display:none;"></div>
        <div class="divider"></div>
        <div id="levelTabs" class="row" style="display:none;"></div>
        <div id="tableOne" class="card" style="margin-top:12px;"></div>

        <div class="divider"></div>
        <div id="trafficLightBlock" style="display:none;">
          <div class="row" style="justify-content:space-between; align-items:center; gap:10px; flex-wrap:wrap;">
            <div class="subtitle" id="trafficLightTitle">Светофор (ColorScore)</div>
          </div>
          <div id="trafficLightTabs" class="row" style="justify-content:flex-start; gap:10px; flex-wrap:wrap; margin-top:10px;"></div>
          <div style="overflow:auto; margin-top:10px;">
            <table>
              <thead>
                <tr>
                  <th>✓</th>
                  <th>ColorScore</th>
                  <th>Кандидат</th>
                  <th>Локация</th>
                  <th>Позиция</th>
                  <th>Телефон</th>
                  <th>Email</th>
                </tr>
              </thead>
              <tbody id="tlTbody"></tbody>
            </table>
          </div>
          <div class="row" style="justify-content:flex-end; margin-top:12px; gap:10px;">
            <button id="btnAddContacts" type="button" disabled>Добавить</button>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div id="resumeModalBackdrop" class="tl-modal-backdrop">
    <div id="resumeModal" class="tl-modal">
      <div class="row" style="justify-content:space-between; align-items:center; gap:14px;">
        <div class="subtitle" id="resumeModalTitle"></div>
        <button id="resumeModalClose" class="secondary" type="button">✕</button>
      </div>
      <div class="divider"></div>
      <div id="resumeModalMeta" class="mono" style="font-size:14px; margin-bottom:12px;"></div>
      <div class="card" style="margin-bottom:12px;">
        <div class="label">Ключевые навыки</div>
        <div id="resumeModalSkills" class="mono" style="font-size:14px; margin-top:8px;"></div>
      </div>
      <div class="card" style="margin-bottom:12px; display:none;" id="resumeModalSkillsTextWrap">
        <div class="label">Описание навыков</div>
        <pre id="resumeModalSkillsText" class="mono" style="white-space:pre-wrap; font-size:13px; margin-top:8px;"></pre>
      </div>
      <div class="card">
        <div class="label">Опыт работы</div>
        <div id="resumeModalExperience" style="margin-top:8px;"></div>
      </div>
      <div class="card" style="margin-top:12px; display:none;" id="resumeModalEducationWrap">
        <div class="label">Образование</div>
        <div id="resumeModalEducation" style="margin-top:8px;"></div>
      </div>
      <div class="subtitle" style="margin-top:12px; color:#666;">Контакты скрыты. Открыть можно после светофора.</div>
    </div>
  </div>

  <div id="contactsModalBackdrop" class="tl-modal-backdrop">
    <div id="contactsModal" class="tl-modal">
      <div class="row" style="justify-content:space-between; align-items:center; gap:14px;">
        <div class="subtitle" id="contactsModalTitle"></div>
        <button id="contactsModalClose" class="secondary" type="button">✕</button>
      </div>
      <div class="divider"></div>
      <div id="contactsModalBody" class="mono" style="font-size:15px; line-height:1.6;"></div>
    </div>
  </div>

  <div id="tlModalBackdrop" class="tl-modal-backdrop">
    <div id="tlModal" class="tl-modal">
      <div class="row" style="justify-content:space-between; align-items:center; gap:14px;">
        <div style="display:flex; align-items:center; gap:12px;">
          <div class="subtitle" id="tlModalTitle"></div>
          <div id="tlModalStatusCircle" title="Итоговый ColorScore" style="width:24px; height:24px; border-radius:50%; background:#ddf8e7; border:2px solid #0b8a3a; display:flex; align-items:center; justify-content:center; font-weight:800;">✓</div>
        </div>
        <button id="tlModalClose" class="secondary" type="button">✕</button>
      </div>
      <div class="divider"></div>
      <div class="row" style="justify-content:flex-end; gap:10px; margin-top:6px; margin-bottom:10px;">
        <button id="tlModalPromptBtn" class="secondary" type="button">Промпт</button>
        <button id="tlModalAgentRespBtn" class="secondary" type="button">Ответ агента</button>
      </div>

      <div id="tlModalTableWrap" style="overflow:auto; max-height:65vh;">
        <div class="card">
          <div class="label">Светофор (ColorScore)</div>
          <div style="overflow:auto; margin-top:8px;">
            <table>
              <thead>
                <tr>
                  <th>Требование</th>
                  <th>Резюме</th>
                  <th>Итог</th>
                  <th>Несоответствие</th>
                </tr>
              </thead>
              <tbody id="tlModalTbody"></tbody>
            </table>
          </div>
        </div>
      </div>

      <div id="tlModalPromptWrap" class="llm" style="display:none; overflow:auto; max-height:65vh;">
        <div class="subtitle" style="color:#000; margin-bottom:10px;">Итоговый промпт (отправляется LLM)</div>
        <pre id="tlModalPromptText" class="mono" style="white-space:pre-wrap; font-size:13px; margin:0;"></pre>
      </div>

      <div id="tlModalAgentRespWrap" class="llm" style="display:none; overflow:auto; max-height:65vh;">
        <div class="subtitle" style="color:#000; margin-bottom:10px;">Ответ агента (raw)</div>
        <pre id="tlModalAgentRespText" class="mono" style="white-space:pre-wrap; font-size:13px; margin:0;"></pre>
      </div>
    </div>
  </div>

<script>
  const el = (id) => document.getElementById(id);
  const NL = String.fromCharCode(10);
  const NNL = NL + NL;
  const state = {
    candidates: [],
    foundCount: 0,
    query: "",
    trafficLightById: null,
    trafficLightCandidates: [],
    trafficLightCandidatesLast: [],
    startedAt: null,
    boolFinishedAt: null,
    hhFinishedAt: null,
    finishedAt: null,
    stageAttempts: [],
    totalIterations: 0,
    promptRestarts: 0,
    selectedCandidateIds: new Set(),
    selectedTrafficLightIds: new Set(),
    contactsById: {},
    sessionId: null,
    finalSearchUrl: null,
  };

  function setStatus(text) { el("status").textContent = text || ""; }
  function setBusy(b) {
    el("btnDefault").disabled = b;
    el("btnBool").disabled = b;
    el("btnSearch").disabled = b;
    const candT = el("candLimit");
    if (candT) candT.disabled = b;
    ["area113", "area16"].forEach((id) => {
      const t = el(id);
      if (t) t.disabled = b;
    });
    const extraIds = ["btnScreening", "btnAddContacts"];
    extraIds.forEach((id) => {
      const t = el(id);
      if (t) t.disabled = b;
    });
  }

  function getAreaIds() {
    const ids = [];
    if (el("area113")?.checked) ids.push(113);
    if (el("area16")?.checked) ids.push(16);
    return ids.length ? ids : [113, 16];
  }

  function getCandidatesLimit() {
    const t = el("candLimit");
    const v = t ? Number(t.value) : 10;
    if (!Number.isFinite(v) || v <= 0) return 10;
    return Math.min(200, Math.max(1, v));
  }

  function getSearchTargetCount() {
    return Math.min(200, getCandidatesLimit() * 3);
  }

  function candidatePersonalName(c) {
    return ((c?.last_name || "") + " " + (c?.first_name || "")).trim();
  }

  function candidateNameOrId(c) {
    const personal = candidatePersonalName(c);
    if (personal) return personal;
    const id = String(c?.id ?? "");
    const title = String(c?.title ?? "").trim();
    const cn = String(c?.candidate_name ?? "").trim();
    if (cn && cn !== title) return cn;
    return id || "-";
  }

  function candidateDisplayName(c) {
    return candidateNameOrId(c);
  }

  function candidatePosition(c) {
    return String(c?.title || "").trim();
  }

  function sortTrafficLightByScore(items) {
    return [...(Array.isArray(items) ? items : [])].sort(
      (a, b) => Number(b?.color_score_percent ?? 0) - Number(a?.color_score_percent ?? 0)
    );
  }

  function extractSkillsFromResume(r) {
    const skillSet = Array.isArray(r?.skill_set) ? r.skill_set : [];
    const names = skillSet.map((s) => s?.name).filter(Boolean);
    if (names.length) return names;
    if (Array.isArray(r?.skills)) return r.skills.map(String).filter(Boolean);
    return [];
  }

  function normalizeExperienceFromResume(r) {
    const exp = r?.experience;
    return Array.isArray(exp) ? exp : [];
  }

  function candidateFromApiItem(item) {
    const resume = item?.resume_json && typeof item.resume_json === "object" ? item.resume_json : {};
    const id = String(item?.id || resume?.id || "");
    return {
      id,
      resume_json: resume,
      first_name: resume.first_name,
      last_name: resume.last_name,
      title: resume.title,
      age: resume.age,
      area: resume.area,
      salary: resume.salary,
      skills: extractSkillsFromResume(resume),
      skills_text: typeof resume.skills === "string" ? resume.skills : null,
      education: Array.isArray(resume.education) ? resume.education : [],
      experience_full: normalizeExperienceFromResume(resume),
    };
  }

  function tlItemToModalCandidate(c) {
    return {
      id: c?.id,
      candidate_name: c?.candidate_name,
      title: c?.title,
      location: c?.location,
      color_score_percent: c?.color_score_percent,
      requirements: c?.requirements,
      debug_prompt: c?.prompt,
      debug_llm_raw: c?.llm_raw,
    };
  }
  function formatSalary(c) {
    const s = c?.salary;
    if (!s) return "";
    if (typeof s === "object" && s.amount) return `${s.amount} ${s.currency || ""}`.trim();
    try { return JSON.stringify(s); } catch (e) { return String(s); }
  }

  function formatSkills(c) {
    const skills = Array.isArray(c?.skills) ? c.skills : [];
    return skills.map((x) => (typeof x === "string" ? x : x?.name)).filter(Boolean).join(", ");
  }

  function updateSelectionButtons() {
    const btnScreening = el("btnScreening");
    if (btnScreening) btnScreening.disabled = state.selectedCandidateIds.size <= 0;
    const btnAddContacts = el("btnAddContacts");
    if (btnAddContacts) btnAddContacts.disabled = state.selectedTrafficLightIds.size <= 0;
  }

  function formatContactItem(item) {
    if (!item || typeof item !== "object") return "";
    const typeName = item?.type?.name || item?.type?.id || "";
    const kind = String(item?.kind || "").trim();
    const label = typeName || kind || "контакт";
    const preferred = item?.preferred ? " (предпочтительный)" : "";
    const value = String(item?.contact_value || "").trim();
    const comment = String(item?.comment || "").trim();
    const parts = [`${label}${preferred}`];
    if (value) parts.push(value);
    if (comment) parts.push(`комментарий: ${comment}`);
    if (item?.verified === true) parts.push("подтверждён");
    if (item?.need_verification === true) parts.push("требует подтверждения");
    return parts.join(" — ");
  }

  function extractContactsFromResume(resume) {
    let phone = null;
    let email = null;
    const raw = [];
    const contact = resume?.contact;
    if (!Array.isArray(contact)) {
      return { phone, email, contacts: raw };
    }
    contact.forEach((item) => {
      if (!item || typeof item !== "object") return;
      raw.push(item);
      const value = String(item?.contact_value || "").trim();
      if (!value) return;
      const typeId = String(item?.type?.id || item?.type || "").toLowerCase();
      const kind = String(item?.kind || "").toLowerCase();
      if (!email && (kind === "email" || typeId === "email")) email = value;
      else if (!phone && (kind === "phone" || ["cell", "home", "work", "phone"].includes(typeId))) phone = value;
    });
    if (!phone && resume?.phone) phone = String(resume.phone);
    if (!email && resume?.email) email = String(resume.email);
    return { phone, email, contacts: raw };
  }

  function stage3ItemToContactInfo(item) {
    const tl = item?.traffic_light || {};
    const resume = item?.resume_json || {};
    const id = String(tl?.id || resume?.id || "");
    const extracted = extractContactsFromResume(resume);
    return {
      id,
      candidate_name: tl?.candidate_name || resume?.last_name && resume?.first_name
        ? `${resume.last_name} ${resume.first_name}`.trim()
        : id,
      phone: extracted.phone,
      email: extracted.email,
      contacts: extracted.contacts,
      error: item?.error || null,
      resume_json: resume,
    };
  }

  function openContactsModal(contactInfo) {
    const backdrop = el("contactsModalBackdrop");
    const title = el("contactsModalTitle");
    const body = el("contactsModalBody");
    if (!backdrop || !title || !body) return;
    title.textContent = contactInfo?.candidate_name || contactInfo?.id || "Контакты";
    const lines = [];
    if (contactInfo?.phone) lines.push(`Телефон: ${contactInfo.phone}`);
    if (contactInfo?.email) lines.push(`Email: ${contactInfo.email}`);
    const raw = Array.isArray(contactInfo?.contacts) ? contactInfo.contacts : [];
    raw.forEach((item) => {
      const line = formatContactItem(item);
      if (line) lines.push(line);
    });
    if (contactInfo?.error) lines.push(`Ошибка: ${contactInfo.error}`);
    if (!lines.length) lines.push("Контакты не найдены");
    body.textContent = lines.join(NL);
    backdrop.style.display = "flex";
  }

  function contactCellHtml(contactInfo, field) {
    if (field === "phone" && contactInfo?.error) {
      return `<span class="mono" data-open-contacts="1" data-contact-id="${escapeHtml(String(contactInfo?.id || ""))}" style="cursor:pointer; color:#c00;">${escapeHtml(contactInfo.error)}</span>`;
    }
    const value = field === "phone" ? contactInfo?.phone : contactInfo?.email;
    if (!value) return "—";
    const id = String(contactInfo?.id || "");
    return `<span class="mono" data-open-contacts="1" data-contact-id="${escapeHtml(id)}" style="cursor:pointer; color:#1e73ff; text-decoration:underline;">${escapeHtml(value)}</span>`;
  }

  function wireContactCells(tr) {
    tr.querySelectorAll("[data-open-contacts]").forEach((node) => {
      node.onclick = (e) => {
        e.stopPropagation();
        const cid = String(node.getAttribute("data-contact-id") || "");
        if (!cid || !state.contactsById[cid]) return;
        openContactsModal(state.contactsById[cid]);
      };
    });
  }

  async function runAddContactsForSelected() {
    if (!state.sessionId) {
      setStatus("Сначала выполните поиск");
      return;
    }
    const selectedIds = [...state.selectedTrafficLightIds];
    if (!selectedIds.length) {
      setStatus("Выберите кандидатов для открытия контактов");
      return;
    }
    setBusy(true);
    setStatus(`Открытие контактов (платно): ${selectedIds.length} кандидатов...`);
    try {
      const data = await api("/api/contacts", {
        session_id: state.sessionId,
        candidate_ids: selectedIds,
      });
      const items = Array.isArray(data.candidates) ? data.candidates : [];
      let ok = 0;
      let failed = 0;
      items.forEach((it) => {
        const contactInfo = stage3ItemToContactInfo(it);
        const cid = String(contactInfo?.id ?? "");
        if (!cid) return;
        state.contactsById[cid] = contactInfo;
        if (contactInfo?.error) failed += 1;
        else ok += 1;
      });
      renderTrafficLightTable(state.trafficLightCandidates);
      setStatus(`Контакты: успешно ${ok}, ошибок ${failed}.`);
    } catch (e) {
      setStatus("Ошибка: " + e.message);
    } finally {
      setBusy(false);
    }
  }

  const btnAddContacts = el("btnAddContacts");
  if (btnAddContacts) btnAddContacts.onclick = async () => { await runAddContactsForSelected(); };

  el("contactsModalClose").onclick = () => { el("contactsModalBackdrop").style.display = "none"; };
  el("contactsModalBackdrop").onclick = (e) => {
    if (e?.target === el("contactsModalBackdrop")) el("contactsModalBackdrop").style.display = "none";
  };

  function openResumeModal(c) {
    const backdrop = el("resumeModalBackdrop");
    const title = el("resumeModalTitle");
    const meta = el("resumeModalMeta");
    const skillsEl = el("resumeModalSkills");
    const skillsTextWrap = el("resumeModalSkillsTextWrap");
    const skillsTextEl = el("resumeModalSkillsText");
    const expWrap = el("resumeModalExperience");
    const eduWrap = el("resumeModalEducationWrap");
    const eduEl = el("resumeModalEducation");

    const name = candidateDisplayName(c);
    title.textContent = name;
    const area = c?.area?.name || c?.area?.id || "";
    const metaParts = [
      c?.title ? `Позиция: ${c.title}` : "",
      area ? `Локация: ${area}` : "",
      c?.age ? `Возраст: ${c.age}` : "",
      formatSalary(c) ? `ЗП: ${formatSalary(c)}` : "",
    ].filter(Boolean);
    meta.textContent = metaParts.join(" · ");

    skillsEl.textContent = formatSkills(c) || "—";
    const skillsText = String(c?.skills_text || "").trim();
    if (skillsTextWrap && skillsTextEl) {
      skillsTextWrap.style.display = skillsText ? "block" : "none";
      skillsTextEl.textContent = skillsText;
    }

    const fullExp = Array.isArray(c?.experience_full) ? c.experience_full : [];
    if (expWrap) {
      expWrap.innerHTML = "";
      if (!fullExp.length) {
        expWrap.innerHTML = `<div class="mono" style="color:#666;">Опыт не загружен</div>`;
      } else {
        fullExp.forEach((it) => {
          const block = document.createElement("div");
          block.style.marginBottom = "14px";
          block.style.paddingBottom = "12px";
          block.style.borderBottom = "1px dashed #ccc";
          const period = [it?.start, it?.end].filter(Boolean).join(" — ");
          const header = [period, it?.company, it?.position].filter(Boolean).join(" | ");
          const desc = String(it?.description || "").trim();
          block.innerHTML = `
            <div class="mono" style="font-weight:700; margin-bottom:6px;">${escapeHtml(header)}</div>
            ${desc ? `<pre class="mono" style="white-space:pre-wrap; font-size:13px; margin:0;">${escapeHtml(desc)}</pre>` : ""}
          `;
          expWrap.appendChild(block);
        });
      }
    }

    const education = Array.isArray(c?.education) ? c.education : [];
    if (eduWrap && eduEl) {
      if (!education.length) {
        eduWrap.style.display = "none";
        eduEl.innerHTML = "";
      } else {
        eduWrap.style.display = "block";
        eduEl.innerHTML = education.map((ed) => {
          const nameEd = ed?.name || ed?.organization || "";
          const result = ed?.result || ed?.specialty || "";
          const year = ed?.year || "";
          return `<div class="mono" style="margin-bottom:8px;">${escapeHtml([nameEd, result, year].filter(Boolean).join(" · "))}</div>`;
        }).join("");
      }
    }

    backdrop.style.display = "flex";
  }

  el("resumeModalClose").onclick = () => { el("resumeModalBackdrop").style.display = "none"; };
  el("resumeModalBackdrop").onclick = (e) => {
    if (e?.target === el("resumeModalBackdrop")) el("resumeModalBackdrop").style.display = "none";
  };

  function getIntInput(id, def, minV, maxV) {
    const t = el(id);
    const v = t ? Number(t.value) : def;
    if (!Number.isFinite(v)) return def;
    return Math.min(maxV, Math.max(minV, Math.trunc(v)));
  }

  // Светофор запускается по выбранным кандидатам через /api/traffic_light.

  function tlColorForScore(score) {
    const s = Number(score ?? 0);
    if (s >= 60) return "#ddf8e7";
    if (s >= 40) return "#feeac3";
    return "rgba(255,120,117,.3)";
  }

  function tlColorForMatch(match) {
    const m = Number(match ?? 0);
    if (m >= 70) return "#ddf8e7";
    if (m >= 30) return "#feeac3";
    return "rgba(255,120,117,.3)";
  }

  function buildTrafficLightRow(c) {
    const id = String(c.id ?? "");
    const score = Number(c.color_score_percent ?? 0);
    const rectBg = tlColorForScore(score);
    const circleBorder = score >= 60 ? "#0b8a3a" : (score >= 40 ? "#d9b000" : "#ff4d4d");
    const candidateName = String(c.candidate_name || candidateNameOrId(c));
    const location = c.location ?? "";
    const position = candidatePosition(c);
    const contactInfo = state.contactsById[id] || null;

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>
        <input type="checkbox" data-tl-select="1" ${state.selectedTrafficLightIds.has(id) ? "checked" : ""} ${id ? "" : "disabled"} />
      </td>
      <td>
        <div class="tl-rect" style="background:${rectBg}; border-color:${circleBorder};" title="ColorScore">
          <div class="mono" style="font-size:16px; line-height:1;">${escapeHtml(String(score))}%</div>
        </div>
      </td>
      <td class="mono">${escapeHtml(candidateName)}</td>
      <td>${escapeHtml(location)}</td>
      <td>${escapeHtml(position)}</td>
      <td>${contactCellHtml(contactInfo, "phone")}</td>
      <td>${contactCellHtml(contactInfo, "email")}</td>
    `;

    const chk = tr.querySelector('input[data-tl-select="1"]');
    if (chk) {
      chk.onchange = () => {
        if (!id) return;
        if (chk.checked) state.selectedTrafficLightIds.add(id);
        else state.selectedTrafficLightIds.delete(id);
        updateSelectionButtons();
      };
    }

    const rect = tr.querySelector(".tl-rect");
    if (rect) rect.onclick = () => openTrafficLightModal(tlItemToModalCandidate(c), "table");

    wireContactCells(tr);
    return tr;
  }

  function renderTrafficLightTable(items) {
    const block = el("trafficLightBlock");
    const titleEl = el("trafficLightTitle");
    const tbody = el("tlTbody");
    state.trafficLightById = {};
    tbody.innerHTML = "";

    const list = sortTrafficLightByScore(items);
    state.trafficLightCandidates = [...list];
    block.style.display = list.length ? "block" : "none";
    if (titleEl) titleEl.textContent = "Светофор (ColorScore) — выберите кандидатов и нажмите «Добавить» для контактов (платно)";

    list.forEach((c) => {
      const id = String(c.id ?? "");
      const tr = buildTrafficLightRow(c);
      state.trafficLightById[id] = c;
      tbody.appendChild(tr);
    });
    updateSelectionButtons();
  }

  function renderTrafficLightTableInto(levelName, items) {
    const idx = String(levelName || "main").toLowerCase().replace(/[^a-zа-я0-9]+/gi, "-");
    const block = el(`trafficLightBlock-${idx}`);
    const tbody = el(`tlTbody-${idx}`);
    if (!block || !tbody) return;

    state.trafficLightById = {};
    tbody.innerHTML = "";

    const list = sortTrafficLightByScore(items);
    block.style.display = list.length ? "block" : "none";

    list.forEach((c) => {
      const id = String(c.id ?? "");
      const tr = buildTrafficLightRow(c);
      state.trafficLightById[id] = c;
      tbody.appendChild(tr);
    });
    updateSelectionButtons();
  }

  function showTlModalTab(tab) {
    const tableWrap = el("tlModalTableWrap");
    const promptWrap = el("tlModalPromptWrap");
    const agentRespWrap = el("tlModalAgentRespWrap");

    if (tableWrap) tableWrap.style.display = tab === "table" ? "block" : "none";
    if (promptWrap) promptWrap.style.display = tab === "prompt" ? "block" : "none";
    if (agentRespWrap) agentRespWrap.style.display = tab === "agentResponse" ? "block" : "none";
  }

  function openTrafficLightModal(c, initialTab = "table") {
    const backdrop = el("tlModalBackdrop");
    const title = el("tlModalTitle");
    const tbody = el("tlModalTbody");
    const statusCircle = el("tlModalStatusCircle");
    const promptTextEl = el("tlModalPromptText");
    const agentRespTextEl = el("tlModalAgentRespText");

    const candidateName = candidateNameOrId(c);
    const titleText = candidatePosition(c) ? `${candidateName} — ${candidatePosition(c)}` : candidateName;
    title.textContent = titleText;

    if (statusCircle) {
      const score = Number(c?.color_score_percent ?? 0);
      const bg = tlColorForScore(score);
      const borderColor = score >= 60 ? "#0b8a3a" : (score >= 40 ? "#d9b000" : "#ff4d4d");
      statusCircle.style.background = bg;
      statusCircle.style.border = `2px solid ${borderColor}`;
    }

    const reqs = Array.isArray(c?.requirements) ? c.requirements : [];
    tbody.innerHTML = "";
    reqs.forEach((it) => {
      const mp = Number(it.match_percent ?? 0);
      const color = tlColorForMatch(mp);
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${escapeHtml(it.requirement ?? "")}</td>
        <td>${escapeHtml(it.resume_evidence ?? "")}</td>
        <td>
          <div style="background:${color}; padding:6px; border:1px solid #000; width:100px; text-align:center;">
            ${escapeHtml(String(mp))}%
          </div>
        </td>
        <td>${escapeHtml(it.difference_comment ?? "")}</td>
      `;
      tbody.appendChild(tr);
    });

    if (promptTextEl) {
      promptTextEl.textContent = String(c?.debug_prompt ?? "");
    }
    if (agentRespTextEl) {
      const raw = c?.debug_llm_raw ?? null;
      if (raw === null || raw === undefined) {
        agentRespTextEl.textContent = "";
      } else {
        try {
          agentRespTextEl.textContent = typeof raw === "string" ? raw : JSON.stringify(raw, null, 2);
        } catch (e) {
          agentRespTextEl.textContent = String(raw);
        }
      }
    }

    showTlModalTab(initialTab);
    backdrop.style.display = "flex";
  }

  // Close modal handlers
  el("tlModalClose").onclick = () => { el("tlModalBackdrop").style.display = "none"; };
  el("tlModalPromptBtn").onclick = () => showTlModalTab("prompt");
  el("tlModalAgentRespBtn").onclick = () => showTlModalTab("agentResponse");
  el("tlModalBackdrop").onclick = (e) => {
    if (e?.target === el("tlModalBackdrop")) el("tlModalBackdrop").style.display = "none";
  };
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") el("tlModalBackdrop").style.display = "none";
  });

  function renderQueries(query, finalUrl) {
    const q = el("queries");
    q.innerHTML = "";
    const text = String(query || "");
    const div = document.createElement("div");
    div.className = "card";
    div.innerHTML = `
      <div class="label">Итоговый запрос</div>
      <div class="mono big">${escapeHtml(text)}</div>
    `;
    q.appendChild(div);
    q.style.display = "grid";
    renderQueryLinks(text, finalUrl || buildHhSearchUrl(text));
  }

  function renderFinalQueryInfo() {
    const box = el("finalQueryInfo");
    if (!box) return;
    const q = state.query || "";
    const attempts = Array.isArray(state.stageAttempts) ? state.stageAttempts : [];
    if (!q && !attempts.length) {
      box.style.display = "none";
      box.innerHTML = "";
      return;
    }
    const attemptsRows = attempts.map((it) => {
      const stage = escapeHtml(it.stage || "");
      const query = escapeHtml(it.query || "");
      const found = Number(it.found || 0);
      const collected = Number(it.collected || 0);
      const target = Number(it.target || 0);
      const enough = !!it.enough;
      const err = String(it.error || "").trim();
      const result = err ? `Ошибка HH: ${escapeHtml(err)}` : (enough ? "Хватило" : "Меньше нужного");
      return `<tr>
        <td>${stage}</td>
        <td class="mono">${query}</td>
        <td>${found}</td>
        <td>${collected} / ${target}</td>
        <td>${result}</td>
      </tr>`;
    }).join("");
    box.innerHTML = `
      <div class="label">Итоговый булевый запрос</div>
      <div class="mono big">${escapeHtml(q)}</div>
      <div class="label" style="margin-top:12px;">Этапы ослабления и результаты HH</div>
      <div style="overflow:auto; margin-top:8px;">
        <table>
          <thead><tr><th>Этап</th><th>Запрос</th><th>Найдено</th><th>Накоплено</th><th>Статус</th></tr></thead>
          <tbody>${attemptsRows}</tbody>
        </table>
      </div>
    `;
    box.style.display = "block";
  }

  function buildHhSearchUrl(query) {
    // Ссылка должна соответствовать формату веб-UI HH (без параметра title).
    // Пример "правильно" из ТЗ: text=...&area=113&isDefaultArea=true&pos=full_text&logic=normal&...
    const params = new URLSearchParams();
    params.set("text", query || "");
    params.set("area", "113");
    params.set("isDefaultArea", "true");
    params.set("pos", "full_text");
    params.set("logic", "normal");
    params.set("exp_period", "all_time");
    params.set("ored_clusters", "true");
    params.set("order_by", "relevance");
    params.set("search_period", "0");
    params.set("age_to", "45");
    ["unknown", "active_search", "looking_for_offers"].forEach((v) => params.append("job_search_status", v));
    ["between3And6", "moreThan6"].forEach((v) => params.append("experience", v));
    params.set("items_on_page", "20");
    params.set("hhtmFrom", "resume_search_result");
    params.set("hhtmFromLabel", "resume_search_line");
    return `https://tomsk.hh.ru/search/resume?${params.toString()}`;
  }

  function buildDecodeHtml(query) {
    return `
      <div class="param-group">
        <div class="param-title">Текст и позиция</div>
        <div class="param-item">• text: ${escapeHtml(query || "")}</div>
      </div>
      <div class="param-group">
        <div class="param-title">Локация и период</div>
        <div class="param-item">• area: ${escapeHtml(getAreaIds().join(", "))} (Россия 113, Беларусь 16)</div>
        <div class="param-item">• period/search_period: 0 (за всё время)</div>
      </div>
      <div class="param-group">
        <div class="param-title">Фильтры кандидата</div>
        <div class="param-item">• age_to: 45</div>
        <div class="param-item">• experience: between3And6, moreThan6</div>
        <div class="param-item">• job_search_status: unknown, active_search, looking_for_offers</div>
      </div>
      <div class="param-group">
        <div class="param-title">Пагинация</div>
        <div class="param-item">• per_page/items_on_page: 20</div>
      </div>
    `;
  }

  function truncateMiddle(s, maxLen = 90) {
    const str = String(s || "");
    if (str.length <= maxLen) return str;
    const keep = Math.max(10, Math.floor((maxLen - 3) / 2));
    return `${str.slice(0, keep)}...${str.slice(str.length - keep)}`;
  }

  function truncateEnd(s, maxLen = 25) {
    const str = String(s || "");
    if (str.length <= maxLen) return str;
    return `${str.slice(0, maxLen)}...`;
  }

  function renderQueryLinks(queryText, href) {
    const wrap = el("queryLinks");
    wrap.innerHTML = "";
    const div = document.createElement("div");
    div.className = "card";
    div.innerHTML = `
      <div class="label">Итоговая ссылка в HH</div>
      <div class="mono link-preview" title="${escapeHtml(href)}">${escapeHtml(truncateMiddle(href))}</div>
      <div class="row">
        <button class="secondary" type="button" data-action="copy">Копировать</button>
        <button type="button" data-action="open">Перейти</button>
        <button class="secondary" type="button" data-action="decode">Расшифровка</button>
      </div>
      <div class="param-block" data-role="decode"></div>
    `;
    const copyBtn = div.querySelector('[data-action="copy"]');
    const openBtn = div.querySelector('[data-action="open"]');
    const decodeBtn = div.querySelector('[data-action="decode"]');
    const decodeBox = div.querySelector('[data-role="decode"]');
    copyBtn?.addEventListener("click", async () => {
      try {
        if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(href);
        setStatus("Ссылка скопирована");
      } catch (e) {
        setStatus("Не удалось скопировать ссылку");
      }
    });
    openBtn?.addEventListener("click", () => window.open(href, "_blank", "noopener,noreferrer"));
    decodeBtn?.addEventListener("click", () => {
      if (!decodeBox) return;
      const shown = decodeBox.style.display === "block";
      decodeBox.style.display = shown ? "none" : "block";
      if (!shown) decodeBox.innerHTML = buildDecodeHtml(queryText || "");
    });
    wrap.appendChild(div);
    wrap.style.display = "flex";
  }

  function renderActiveLevelTable() {
    const host = el("tableOne");
    if (!host) return;
    const idx = "main";
    const list = Array.isArray(state.candidates) ? state.candidates : [];

    host.innerHTML = `
      <div class="card" style="margin-top:0;">
        <div style="overflow:auto; margin-top:10px;">
          <table>
            <thead>
              <tr>
                <th>✓</th>
                <th>Имя</th>
                <th>Позиция</th>
                <th>Локация</th>
                <th>Возраст</th>
                <th>ЗП</th>
                <th>Ключевые навыки</th>
                <th>Скачать</th>
              </tr>
            </thead>
            <tbody id="tbody-level-${escapeHtml(idx)}"></tbody>
          </table>
        </div>
        <div class="row" style="justify-content:flex-end; margin-top:12px; gap:10px;">
          <button id="btnScreening" type="button" disabled>Далее</button>
        </div>
      </div>
    `;

    const tbody = host.querySelector(`#tbody-level-${idx}`);
    (list || []).forEach((c) => {
      const area = c.area?.name || c.area?.id || "";
      const salary = formatSalary(c);
      const skillsText = truncateEnd(formatSkills(c), 80);
      const nameLabel = truncateEnd(candidateNameOrId(c), 25);
      const position = truncateEnd(candidatePosition(c), 40);
      const cid = String(c.id || "");
      const pdfHref = cid ? `/api/resumes/${encodeURIComponent(cid)}/pdf` : "";
      const pdfCell = pdfHref
        ? `<a href="${escapeHtml(pdfHref)}" download="resume_${escapeHtml(cid)}.pdf" title="Скачать PDF резюме">Скачать</a>`
        : `<span class="mono" style="opacity:0.5;">—</span>`;

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>
          <input type="checkbox" data-select="1" ${state.selectedCandidateIds.has(cid) ? "checked" : ""} ${cid ? "" : "disabled"} />
        </td>
        <td class="mono" data-open-resume="1" title="${escapeHtml(candidateNameOrId(c))}" style="cursor:pointer; color:#1e73ff; text-decoration:underline;">${escapeHtml(nameLabel)}</td>
        <td>${escapeHtml(position)}</td>
        <td>${escapeHtml(area)}</td>
        <td>${c.age ?? ""}</td>
        <td class="mono">${escapeHtml(salary || "")}</td>
        <td class="mono" title="${escapeHtml(formatSkills(c))}">${escapeHtml(skillsText || "—")}</td>
        <td class="cell-actions-td">
          <div class="cell-actions">${pdfCell}</div>
        </td>
      `;
      const chk = tr.querySelector('input[data-select="1"]');
      if (chk) {
        chk.onchange = () => {
          if (!cid) return;
          if (chk.checked) state.selectedCandidateIds.add(cid);
          else state.selectedCandidateIds.delete(cid);
          updateSelectionButtons();
        };
      }
      const nameEl = tr.querySelector('[data-open-resume="1"]');
      if (nameEl) {
        nameEl.onclick = () => openResumeModal(c);
      }
      tbody?.appendChild(tr);
    });

    const btnScreening = el("btnScreening");
    if (btnScreening) {
      btnScreening.onclick = async () => { await runTrafficLightForSelected(); };
    }
    updateSelectionButtons();
  }

  async function runTrafficLightForSelected() {
    if (!state.sessionId) {
      setStatus("Сначала выполните поиск");
      return;
    }
    const list = Array.isArray(state.candidates) ? state.candidates : [];
    const selectedIds = list
      .filter((c) => state.selectedCandidateIds.has(String(c.id || "")))
      .map((c) => String(c.id || ""));
    if (!selectedIds.length) {
      setStatus("Выберите кандидатов для светофора");
      return;
    }
    setBusy(true);
    setStatus(`Светофор: ${selectedIds.length} кандидатов...`);
    try {
      const data = await api("/api/traffic_light", {
        session_id: state.sessionId,
        candidate_ids: selectedIds,
      });
      const tlItems = Array.isArray(data.candidates) ? data.candidates : [];
      state.selectedTrafficLightIds = new Set();
      renderTrafficLightTable(tlItems);
      const tlBlock = el("trafficLightBlock");
      if (tlBlock) tlBlock.style.display = "block";
      setStatus("Готово.");
    } catch (e) {
      setStatus("Ошибка светофора: " + e.message);
    } finally {
      setBusy(false);
    }
  }

  function escapeHtml(s) {
    return String(s)
      .replaceAll("&","&amp;")
      .replaceAll("<","&lt;")
      .replaceAll(">","&gt;")
      .replaceAll('"',"&quot;")
      .replaceAll("'","&#039;");
  }

  let progressTimer = null;
  function stopProgress() {
    if (progressTimer) {
      clearInterval(progressTimer);
      progressTimer = null;
    }
  }

  function startProgress(stage1Name, stage1Sec, stage2Name, stage2Sec, stage3Name, stage3Sec, totalSec) {
    stopProgress();
    const startedAt = Date.now();
    const s1End = Math.max(0, Number(stage1Sec) || 0);
    const s2End = s1End + Math.max(0, Number(stage2Sec) || 0);
    const s3End = s2End + Math.max(0, Number(stage3Sec) || 0);
    const ends = [s1End, s2End, s3End];
    const names = [stage1Name, stage2Name, stage3Name];
    const total = Math.max(1, Number(totalSec) || s3End || 1);

    function tick() {
      const elapsed = (Date.now() - startedAt) / 1000;
      let stageIdx = 0;
      if (elapsed >= s3End) stageIdx = 2;
      else if (elapsed >= s2End) stageIdx = 2;
      else if (elapsed >= s1End) stageIdx = 1;
      const stageEnd = ends[Math.min(2, stageIdx)];
      const ps = el("progressStage");
      const pt = el("progressTimes");
      if (ps) ps.textContent = names[stageIdx] || "";
      if (pt) {
        pt.textContent = `Прошло: ${Math.floor(elapsed)}s | Итераций: ${state.totalIterations || 0} | Перезапусков промпта: ${state.promptRestarts || 0}`;
      }
      if (elapsed >= total) stopProgress();
    }

    tick();
    progressTimer = setInterval(tick, 400);
  }

  async function api(path, body) {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const t = await res.text();
      throw new Error(`${res.status}: ${t}`);
    }
    return await res.json();
  }


  el("btnDefault").onclick = async () => {
    setBusy(true); setStatus("Загружаю запрос по умолчанию...");
    try {
      const res = await fetch("/api/default_request");
      const txt = await res.text();
      el("requestText").value = txt;
      setStatus("Готово.");
    } catch (e) {
      setStatus("Ошибка: " + e.message);
    } finally { setBusy(false); }
  };

  el("btnBool").onclick = async () => {
    const requestText = el("requestText").value.trim();
    setBusy(true); setStatus("Получаю булевы запросы...");
    try {
      const data = await api("/api/generate_queries", {
        request_text: requestText,
      });
      renderQueries(data.query, null);
      el("results").style.display = "none";
      el("trafficLightBlock").style.display = "none";
      const tbody = el("tlTbody");
      if (tbody) tbody.innerHTML = "";
      state.trafficLightById = null;
      setStatus("Готово.");
    } catch (e) {
      setStatus("Ошибка: " + e.message);
    } finally { setBusy(false); }
  };

  el("btnSearch").onclick = async () => {
    const requestText = el("requestText").value.trim();
    setBusy(true); setStatus("Поиск: LLM → HH → просмотр резюме...");
    const limit = getCandidatesLimit();
    const target = getSearchTargetCount();
    const stage1Sec = 12;
    const stage2Sec = 10;
    const stage3Sec = Math.max(15, Math.ceil(target / 4));
    const totalSec = stage1Sec + stage2Sec + stage3Sec;
    const stage1Name = "Этап 1: генерация булевых запросов";
    const stage2Name = "Этап 2: поиск в HH";
    const stage3Name = `Этап 3: просмотр ${target} резюме (бесплатно)`;
    startProgress(stage1Name, stage1Sec, stage2Name, stage2Sec, stage3Name, stage3Sec, totalSec);
    try {
      state.totalIterations = 0;
      state.promptRestarts = 0;
      const data = await api("/api/search", {
        request_text: requestText,
        candidates_limit: getCandidatesLimit(),
        area_ids: getAreaIds(),
      });
      renderQueries(data.query, data.final_search_url);
      state.sessionId = data.session_id || null;
      state.finalSearchUrl = data.final_search_url || null;
      state.candidates = (Array.isArray(data.candidates) ? data.candidates : []).map(candidateFromApiItem);
      state.foundCount = Number(data.found_count || 0);
      state.query = data.query || "";
      state.startedAt = data.started_at || null;
      state.boolFinishedAt = data.bool_finished_at || null;
      state.hhFinishedAt = data.hh_finished_at || null;
      state.finishedAt = data.finished_at || null;
      state.stageAttempts = data.stage_attempts || [];
      state.totalIterations = Number(data.total_iterations || 0);
      state.promptRestarts = Number(data.prompt_restarts || 0);
      // reset traffic lights
      state.contactsById = {};
      state.selectedCandidateIds = new Set();
      state.selectedTrafficLightIds = new Set();

      el("results").style.display = "block";
      const totalShown = state.candidates.length;
      const needN = getCandidatesLimit();
      const targetN = getSearchTargetCount();
      const sessionLabel = state.sessionId ? `session_id: ${state.sessionId}` : "";
      el("pickedInfo").textContent = `Загружено резюме: ${totalShown} (цель: ${targetN} = ${needN}×3, без контактов). ${sessionLabel}`;
      const tabs = el("levelTabs");
      if (tabs) tabs.style.display = "none";
      renderActiveLevelTable();
      renderFinalQueryInfo();

      const tlBlock = el("trafficLightBlock");
      if (tlBlock) tlBlock.style.display = "none";
      const tlT = el("tlTbody");
      if (tlT) tlT.innerHTML = "";
      const tlTabs = el("trafficLightTabs");
      if (tlTabs) tlTabs.innerHTML = "";
      setStatus("Готово.");

      stopProgress();
      el("progressStage").textContent = "";
      el("progressTimes").textContent = "";
    } catch (e) {
      stopProgress();
      el("progressStage").textContent = "";
      el("progressTimes").textContent = "";
      setStatus("Ошибка: " + e.message);
    } finally { setBusy(false); }
  };

  // btnSvetofor removed by task.

  // legacy /api/svetofor removed

</script>
</body>
</html>
"""

