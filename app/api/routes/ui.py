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
        <div class="title">Поиск резюме (LLM → булевы → HH)</div>
      </div>

      <div class="row" style="justify-content: flex-end;">
        <button id="btnOpenBot" class="secondary" type="button" title="Открыть UI бота (/ui/bot)">
          HH Чат
        </button>
      </div>

      <textarea id="requestText" placeholder="Вставьте запрос/требования..."></textarea>

      <div class="row">
        <div class="stack" style="flex:2; min-width:260px;">
          <div class="row">
            <button class="secondary" id="btnDefault">Запрос по умолчанию</button>
            <button class="secondary" id="btnBool">Получить булевый запрос</button>
            <button id="btnSearch">Поиск</button>
          </div>
        </div>
        <div class="stack" style="flex:3; min-width:260px;">
          <div class="row">
            <label class="pill">
              Кол-во кандидатов в таблице
              <input type="number" id="candLimit" value="20" min="1" max="200" />
            </label>
            <label class="pill">
              Светофор: первые X кандидатов
              <input type="number" id="svetoforTopX" value="20" min="1" max="200" />
            </label>
            <label class="pill">
              Минимальный срок (мес)
              <input type="number" id="minStayMonths" value="3" min="1" max="240" />
            </label>
          </div>
          <div class="row">
            <label class="pill">
              Лимит коротких мест
              <input type="number" id="allowedShortJobs" value="2" min="0" max="50" />
            </label>
            <label class="pill">
              Режим прыгуна
              <select id="jumpMode" style="margin-left:8px;">
                <option value="consecutive">подряд прыгун</option>
                <option value="total">вообще прыгун</option>
              </select>
            </label>
            <label class="pill">
              Максимум не в деле (мес)
              <input type="number" id="maxNotEmployedMonths" value="6" min="0" max="240" />
            </label>
            <label class="pill"><input type="checkbox" id="showPrompt" /> показать промпт</label>
          </div>
        </div>
      </div>

      <div id="status" class="subtitle"></div>
      <div id="progressStage" class="subtitle" style="color:#333;"></div>
      <div id="progressTimes" class="subtitle" style="color:#333;"></div>
      <div id="promptBlock" class="llm" style="display:none;">
        <div class="label subtitle" style="color:#000;">system prompt (редактируемый)</div>
        <textarea id="systemPromptText" class="prompt-editor" placeholder="Здесь можно отредактировать system prompt"></textarea>
        <div class="label subtitle" style="color:#000; margin-top:10px;">user prompt (редактируемый)</div>
        <textarea id="userPromptText" class="prompt-editor" placeholder="Шаблон user prompt, используйте {vac_reqs} для текста запроса"></textarea>
      </div>

      <div id="llmBlock" class="llm" style="display:none;">
        <div class="label subtitle" style="color:#000;">ответ LLM (raw)</div>
        <pre id="llmRaw" class="mono" style="white-space:pre-wrap; font-size:13px;"></pre>
      </div>

      <div id="queries" class="grid3" style="display:none;"></div>
      <div id="queryLinks" class="stack" style="display:none;"></div>

      <div id="results" style="display:none;">
        <div class="divider"></div>
        <div class="subtitle" id="pickedInfo"></div>
        <div class="divider"></div>
        <div id="levelTabs" class="row" style="justify-content:flex-start; gap:10px; flex-wrap:wrap;"></div>
        <div id="tableOne" class="card" style="margin-top:12px;"></div>

        <div class="divider"></div>
        <div id="trafficLightBlock" style="display:none;">
          <div class="row" style="justify-content:space-between; align-items:center; gap:10px; flex-wrap:wrap;">
            <div class="subtitle" id="trafficLightTitle">Светофор (ColorScore)</div>
            <button class="secondary" id="btnDownloadTlExcel" type="button" disabled>Скачать Excel</button>
          </div>
          <div id="trafficLightTabs" class="row" style="justify-content:flex-start; gap:10px; flex-wrap:wrap; margin-top:10px;"></div>
          <div style="overflow:auto; margin-top:10px;">
            <table>
              <thead>
                <tr>
                  <th>Кандидат</th>
                  <th>Локация</th>
                  <th>Позиция</th>
                </tr>
              </thead>
              <tbody id="tlTbody"></tbody>
            </table>
          </div>
        </div>
      </div>

      <div class="row" style="justify-content:center; margin-top:18px;">
        <button class="secondary" id="btnDownloadFullExcel" type="button" disabled>Скачать полный Excel</button>
      </div>
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
        <table>
          <thead>
            <tr>
              <th>Запрос</th>
              <th>Резюме</th>
              <th>Итог</th>
              <th>Несоответствие</th>
            </tr>
          </thead>
          <tbody id="tlModalTbody"></tbody>
        </table>
      </div>

      <div id="tlModalProjectExpWrap" class="llm" style="display:none; overflow:auto; max-height:65vh;">
        <div class="subtitle" style="color:#000; margin-bottom:10px;">Проектный опыт (то, что подставляем в промпт)</div>
        <pre id="tlModalProjectExpText" class="mono" style="white-space:pre-wrap; font-size:13px; margin:0;"></pre>
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
  const state = {
    candidatesByLevel: null,
    foundCounts: null,
    queries: null,
    queriesWithExclusions: null,
    hhSearchUrls: null,
    selectedLevel: "Уровень 2",
    systemPromptLoaded: false,
    userPromptLoaded: false,
    trafficLightById: null,
    trafficLightCandidates: [],
    hasTrafficLightRun: false,
    trafficLightByLevel: {},
    activeTrafficLevel: null,
    excelByLevel: {},
    tlExcelByLevel: {},
    fullExcelBlobUrl: null,
    fullExcelFileName: "",
  };

  function setStatus(text) { el("status").textContent = text || ""; }
  function setBusy(b) {
    el("btnDefault").disabled = b;
    el("btnBool").disabled = b;
    el("btnSearch").disabled = b;
    const candT = el("candLimit");
    if (candT) candT.disabled = b;
    const extraIds = [
      "svetoforTopX",
      "minStayMonths",
      "allowedShortJobs",
      "jumpMode",
      "maxNotEmployedMonths",
      "btnDownloadFullExcel",
      "btnDownloadTlExcel",
    ];
    extraIds.forEach((id) => {
      const t = el(id);
      if (t) t.disabled = b;
    });
    const promptT = el("systemPromptText");
    if (promptT) promptT.disabled = b;
    const userPromptT = el("userPromptText");
    if (userPromptT) userPromptT.disabled = b;
  }

  function getSystemPromptOverride() {
    if (!el("showPrompt").checked) return null;
    return el("systemPromptText").value;
  }

  function getUserPromptOverride() {
    if (!el("showPrompt").checked) return null;
    return el("userPromptText").value;
  }

  function getCandidatesLimit() {
    const t = el("candLimit");
    const v = t ? Number(t.value) : 20;
    if (!Number.isFinite(v) || v <= 0) return 20;
    return Math.min(200, Math.max(1, v));
  }

  function getIntInput(id, def, minV, maxV) {
    const t = el(id);
    const v = t ? Number(t.value) : def;
    if (!Number.isFinite(v)) return def;
    return Math.min(maxV, Math.max(minV, Math.trunc(v)));
  }

  function getSvetoforTopX() {
    return getIntInput("svetoforTopX", 20, 1, 200);
  }

  function getMinStayMonths() {
    return getIntInput("minStayMonths", 3, 1, 240);
  }

  function getAllowedShortJobs() {
    return getIntInput("allowedShortJobs", 2, 0, 50);
  }

  function getMaxNotEmployedMonths() {
    return getIntInput("maxNotEmployedMonths", 6, 0, 240);
  }

  function getJumpMode() {
    const v = el("jumpMode")?.value;
    return v === "total" ? "total" : "consecutive";
  }

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

  function renderTrafficLightTable(items) {
    const block = el("trafficLightBlock");
    const titleEl = el("trafficLightTitle");
    const tbody = el("tlTbody");
    state.trafficLightById = {};
    tbody.innerHTML = "";

    const list = Array.isArray(items) ? items : [];
    state.trafficLightCandidates = [...list];
    block.style.display = list.length ? "block" : "none";
    if (titleEl) {
      const lvl = state.activeTrafficLevel || state.selectedLevel || "";
      titleEl.textContent = lvl ? `Светофор (ColorScore) — ${lvl}` : "Светофор (ColorScore)";
    }

    list.forEach((c) => {
      const id = String(c.id ?? "");
      const score = Number(c.color_score_percent ?? 0);
      const rectBg = tlColorForScore(score);
      const circleBorder = score >= 60 ? "#0b8a3a" : (score >= 40 ? "#d9b000" : "#ff4d4d");
      const resumeUrl = c.resume_url || c.resumeUrl || "";
      const candidateName = c.candidate_name ?? "";
      const location = c.location ?? "";
      const position = c.title ?? "";

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>
          <div style="display:flex; align-items:center; gap:12px;">
            <div class="tl-rect" style="background:${rectBg}; border-color:${circleBorder};" title="ColorScore">
              <div class="mono" style="font-size:16px; line-height:1;">${escapeHtml(String(score))}%</div>
              <div style="width:18px; height:18px; border-radius:50%; border:2px solid ${circleBorder}; background:${rectBg};"></div>
            </div>
            <button
              class="secondary"
              type="button"
              data-write="1"
              ${resumeUrl ? "" : "disabled"}
              style="padding:8px 10px; font-size:12px; text-transform:none; letter-spacing:0; line-height:1; cursor:pointer;"
              title="Написать через страницу бота"
            >
              Написать
            </button>
            <button
              class="secondary"
              type="button"
              data-open-prj-exp="1"
              style="padding:8px 10px; font-size:12px; text-transform:none; letter-spacing:0; line-height:1; cursor:pointer;"
              title="Показать проектный опыт, который подставляется в промпт"
            >
              Опыт
            </button>
            ${resumeUrl ? `<span class="mono" data-open-resume="1" title="Открыть HH" style="color:#1e73ff; font-size:22px; cursor:pointer; line-height:1;">→</span>` : ""}
            <span class="mono">${escapeHtml(candidateName || id)}</span>
          </div>
        </td>
        <td>${escapeHtml(location)}</td>
        <td>${escapeHtml(position)}</td>
      `;

      const rect = tr.querySelector(".tl-rect");
      rect.onclick = () => openTrafficLightModal(c, "table");

      const openResumeEl = tr.querySelector('[data-open-resume="1"]');
      if (openResumeEl) {
        openResumeEl.onclick = (e) => {
          e.stopPropagation();
          if (!resumeUrl) return;
          window.open(resumeUrl, "_blank", "noopener,noreferrer");
        };
      }

      const openPrjExpEl = tr.querySelector('[data-open-prj-exp="1"]');
      if (openPrjExpEl) {
        openPrjExpEl.onclick = (e) => {
          e.stopPropagation();
          openTrafficLightModal(c, "projectExp");
        };
      }
      const writeBtn = tr.querySelector('[data-write="1"]');
      if (writeBtn) {
        writeBtn.onclick = (e) => {
          e.stopPropagation();
          if (!resumeUrl) return;
          openBotPage(resumeUrl);
        };
      }
      state.trafficLightById[id] = c;
      tbody.appendChild(tr);
    });
  }

  function renderTrafficLightTableInto(levelName, items) {
    const idx = levelName === "Уровень 1" ? "1" : (levelName === "Уровень 3" ? "3" : "2");
    const block = el(`trafficLightBlock-${idx}`);
    const tbody = el(`tlTbody-${idx}`);
    if (!block || !tbody) return;

    state.trafficLightById = {};
    tbody.innerHTML = "";

    const list = Array.isArray(items) ? items : [];
    block.style.display = list.length ? "block" : "none";

    list.forEach((c) => {
      const id = String(c.id ?? "");
      const score = Number(c.color_score_percent ?? 0);
      const rectBg = tlColorForScore(score);
      const circleBorder = score >= 60 ? "#0b8a3a" : (score >= 40 ? "#d9b000" : "#ff4d4d");
      const resumeUrl = c.resume_url || c.resumeUrl || "";
      const candidateName = c.candidate_name ?? "";
      const location = c.location ?? "";
      const position = c.title ?? "";

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>
          <div style="display:flex; align-items:center; gap:12px;">
            <div class="tl-rect" style="background:${rectBg}; border-color:${circleBorder};" title="ColorScore">
              <div class="mono" style="font-size:16px; line-height:1;">${escapeHtml(String(score))}%</div>
              <div style="width:18px; height:18px; border-radius:50%; border:2px solid ${circleBorder}; background:${rectBg};"></div>
            </div>
            <button
              class="secondary"
              type="button"
              data-write="1"
              ${resumeUrl ? "" : "disabled"}
              style="padding:8px 10px; font-size:12px; text-transform:none; letter-spacing:0; line-height:1; cursor:pointer;"
              title="Написать через страницу бота"
            >
              Написать
            </button>
            <button
              class="secondary"
              type="button"
              data-open-prj-exp="1"
              style="padding:8px 10px; font-size:12px; text-transform:none; letter-spacing:0; line-height:1; cursor:pointer;"
              title="Показать проектный опыт, который подставляется в промпт"
            >
              Опыт
            </button>
            ${resumeUrl ? `<span class="mono" data-open-resume="1" title="Открыть HH" style="color:#1e73ff; font-size:22px; cursor:pointer; line-height:1;">→</span>` : ""}
            <span class="mono">${escapeHtml(candidateName || id)}</span>
          </div>
        </td>
        <td>${escapeHtml(location)}</td>
        <td>${escapeHtml(position)}</td>
      `;

      const rect = tr.querySelector(".tl-rect");
      rect.onclick = () => openTrafficLightModal(c, "table");

      const openResumeEl = tr.querySelector('[data-open-resume="1"]');
      if (openResumeEl) {
        openResumeEl.onclick = (e) => {
          e.stopPropagation();
          if (!resumeUrl) return;
          window.open(resumeUrl, "_blank", "noopener,noreferrer");
        };
      }

      const openPrjExpEl = tr.querySelector('[data-open-prj-exp="1"]');
      if (openPrjExpEl) {
        openPrjExpEl.onclick = (e) => {
          e.stopPropagation();
          openTrafficLightModal(c, "projectExp");
        };
      }
      const writeBtn = tr.querySelector('[data-write="1"]');
      if (writeBtn) {
        writeBtn.onclick = (e) => {
          e.stopPropagation();
          if (!resumeUrl) return;
          openBotPage(resumeUrl);
        };
      }
      state.trafficLightById[id] = c;
      tbody.appendChild(tr);
    });
  }

  function showTlModalTab(tab) {
    const tableWrap = el("tlModalTableWrap");
    const projectExpWrap = el("tlModalProjectExpWrap");
    const promptWrap = el("tlModalPromptWrap");
    const agentRespWrap = el("tlModalAgentRespWrap");

    if (tableWrap) tableWrap.style.display = tab === "table" ? "block" : "none";
    if (projectExpWrap) projectExpWrap.style.display = tab === "projectExp" ? "block" : "none";
    if (promptWrap) promptWrap.style.display = tab === "prompt" ? "block" : "none";
    if (agentRespWrap) agentRespWrap.style.display = tab === "agentResponse" ? "block" : "none";
  }

  function openTrafficLightModal(c, initialTab = "table") {
    const backdrop = el("tlModalBackdrop");
    const title = el("tlModalTitle");
    const tbody = el("tlModalTbody");
    const statusCircle = el("tlModalStatusCircle");
    const projectExpTextEl = el("tlModalProjectExpText");
    const promptTextEl = el("tlModalPromptText");
    const agentRespTextEl = el("tlModalAgentRespText");

    const candidateName = c?.candidate_name ?? c?.id ?? "";
    const titleText = c?.title ? `${candidateName} — ${c.title}` : candidateName;
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

    if (projectExpTextEl) {
      projectExpTextEl.textContent = String(c?.candidate_prj_exp ?? "");
    }
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

  function renderQueries(queries, hhUrlsByLevel) {
    const q = el("queries");
    q.innerHTML = "";
    ["Уровень 1","Уровень 2","Уровень 3"].forEach((lvl) => {
      const div = document.createElement("div");
      div.className = "card";
      div.innerHTML = `
        <div class="label">${lvl}</div>
        <div class="mono big">${escapeHtml(queries[lvl] || "")}</div>
      `;
      q.appendChild(div);
    });
    q.style.display = "grid";
    renderQueryLinks(queries, hhUrlsByLevel);
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
    // Если бекенд не отдал professional_role — оставляем дефолтные (как в проекте).
    ["96", "113"].forEach((v) => params.append("professional_role", v));
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
        <div class="param-item">• title: ${escapeHtml(query || "")} + anti-lead для неруководящих</div>
      </div>
      <div class="param-group">
        <div class="param-title">Локация и период</div>
        <div class="param-item">• area: 113 (или выбранный area_id)</div>
        <div class="param-item">• period/search_period: 0 (за всё время)</div>
      </div>
      <div class="param-group">
        <div class="param-title">Фильтры кандидата</div>
        <div class="param-item">• age_to: 45</div>
        <div class="param-item">• experience: between3And6, moreThan6</div>
        <div class="param-item">• job_search_status: unknown, active_search, looking_for_offers</div>
      </div>
      <div class="param-group">
        <div class="param-title">Роли и пагинация</div>
        <div class="param-item">• professional_roles: из маппинга/входных ролей</div>
        <div class="param-item">• per_page/items_on_page: 50 (в ссылке), 20 (в API сейчас)</div>
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

  function renderQueryLinks(queries, hhUrlsByLevel) {
    const wrap = el("queryLinks");
    wrap.innerHTML = "";
    ["Уровень 1","Уровень 2","Уровень 3"].forEach((lvl) => {
      const href = (hhUrlsByLevel && hhUrlsByLevel[lvl]) ? hhUrlsByLevel[lvl] : buildHhSearchUrl(queries[lvl] || "");
      const div = document.createElement("div");
      div.className = "card";
      div.innerHTML = `
        <div class="label">${lvl} — ссылка в HH</div>
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
          if (navigator.clipboard?.writeText) {
            await navigator.clipboard.writeText(href);
          } else {
            const ta = document.createElement("textarea");
            ta.value = href;
            document.body.appendChild(ta);
            ta.select();
            document.execCommand("copy");
            document.body.removeChild(ta);
          }
          setStatus(`${lvl}: ссылка скопирована`);
        } catch (e) {
          setStatus("Не удалось скопировать ссылку");
        }
      });
      openBtn?.addEventListener("click", () => {
        window.open(href, "_blank", "noopener,noreferrer");
      });
      decodeBtn?.addEventListener("click", () => {
        if (!decodeBox) return;
        const shown = decodeBox.style.display === "block";
        decodeBox.style.display = shown ? "none" : "block";
        if (!shown) {
          decodeBox.innerHTML = buildDecodeHtml(queries[lvl] || "");
        }
      });
      wrap.appendChild(div);
    });
    wrap.style.display = "flex";
  }

  function renderLevelTabs(foundCounts) {
    const tabs = el("levelTabs");
    if (!tabs) return;
    const levels = ["Уровень 1", "Уровень 2", "Уровень 3"];
    tabs.innerHTML = "";
    levels.forEach((lvl) => {
      const shown = (state.candidatesByLevel?.[lvl] || []).length;
      const found = countForLevel(lvl, foundCounts);
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "level-tab" + (state.selectedLevel === lvl ? " active" : "");
      btn.textContent = `${lvl} (${shown}/${found})`;
      btn.onclick = () => {
        state.selectedLevel = lvl;
        renderLevelTabs(foundCounts);
        renderActiveLevelTable(foundCounts);
      };
      tabs.appendChild(btn);
    });
    tabs.style.display = "flex";
  }

  function normalizeCount(raw, fallback = 0) {
    const n = Number(raw);
    return Number.isFinite(n) && n >= 0 ? n : fallback;
  }

  function countForLevel(levelName, foundCounts) {
    const fallback = (state.candidatesByLevel?.[levelName] || []).length;
    return normalizeCount(foundCounts?.[levelName], fallback);
  }

  function pickDefaultLevelByCounts(foundCounts, threshold = 20) {
    const c1 = countForLevel("Уровень 1", foundCounts);
    const c2 = countForLevel("Уровень 2", foundCounts);
    const c3 = countForLevel("Уровень 3", foundCounts);

    if (c3 >= threshold) return "Уровень 3";
    if (c2 >= threshold) return "Уровень 2";
    if (c1 >= threshold) return "Уровень 1";

    // Фолбэк: показываем таблицу, где больше всего резюме (по данным сервера).
    const best = [
      { lvl: "Уровень 1", c: c1 },
      { lvl: "Уровень 2", c: c2 },
      { lvl: "Уровень 3", c: c3 },
    ].sort((a, b) => (b.c - a.c) || (b.lvl.localeCompare(a.lvl)))[0];
    return best?.lvl || "Уровень 2";
  }

  function renderActiveLevelTable(foundCounts) {
    const host = el("tableOne");
    if (!host) return;
    const lvl = state.selectedLevel || "Уровень 2";
    const idx = lvl === "Уровень 1" ? "1" : (lvl === "Уровень 3" ? "3" : "2");
    const list = (state.candidatesByLevel?.[lvl] || []);
    const count = countForLevel(lvl, foundCounts);

    host.innerHTML = `
      <div class="card" style="margin-top:0;">
        <div class="label">${lvl} — найдено: ${count}; показано: ${list.length}</div>
        <div class="row" style="justify-content:flex-end; gap:10px; flex-wrap:wrap;">
          <button type="button" data-action="svetofor" data-level="${escapeHtml(lvl)}">Светофор</button>
          <button class="secondary" type="button" data-action="excel-level" data-level="${escapeHtml(lvl)}">Скачать Excel</button>
        </div>
        <div style="overflow:auto; margin-top:10px;">
          <table>
            <thead>
              <tr>
                <th>Do</th>
                <th>Имя/ID</th>
                <th>Позиция</th>
                <th>Локация</th>
                <th>Ссылка</th>
                <th>Возраст</th>
                <th>ЗП</th>
              </tr>
            </thead>
            <tbody id="tbody-level-${idx}"></tbody>
          </table>
        </div>
      </div>
    `;

    const btnS = host.querySelector('button[data-action="svetofor"]');
    if (btnS) btnS.onclick = () => runSvetoforForLevel(lvl);
    const btnE = host.querySelector('button[data-action="excel-level"]');
    if (btnE) btnE.onclick = () => downloadExcelSmart(lvl);

    const tbody = host.querySelector(`#tbody-level-${idx}`);
    (list || []).forEach((c) => {
      const area = c.area?.name || c.area?.id || "";
      const link = c.alternate_url || c.url || "";
      const salary = c.salary?.amount ? `${c.salary.amount} ${c.salary.currency||""}` : (c.salary ? JSON.stringify(c.salary) : "");
      const fullNameOrId = (c.first_name || c.last_name)
        ? ((c.last_name||"") + " " + (c.first_name||"")).trim()
        : (c.id||"");
      const nameShort = truncateEnd(fullNameOrId, 25);
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>
          <button
            class="secondary"
            type="button"
            data-write="1"
            ${link ? "" : "disabled"}
            title="Написать в чат через страницу бота"
            style="padding:8px 10px; font-size:12px; text-transform:none; letter-spacing:0; line-height:1; cursor:pointer;"
          >
            ✍
          </button>
        </td>
        <td class="mono" title="${escapeHtml(fullNameOrId)}">${escapeHtml(nameShort)}</td>
        <td>${escapeHtml(c.title || "")}</td>
        <td>${escapeHtml(area)}</td>
        <td class="${link ? "cell-actions-td" : ""}">
          ${link ? `
            <div class="cell-actions" data-link-actions="1">
              <button class="secondary" type="button" data-action="copy-link" title="Скопировать ссылку">Скопировать</button>
              <button type="button" data-action="open-link" title="Открыть ссылку">Перейти</button>
            </div>
          ` : ""}
        </td>
        <td>${c.age ?? ""}</td>
        <td class="mono">${escapeHtml(salary || "")}</td>
      `;
      const btnWrite = tr.querySelector('button[data-write="1"]');
      if (btnWrite) {
        btnWrite.onclick = (e) => {
          e.stopPropagation();
          if (!link) return;
          openBotPage(link);
        };
      }
      const actions = tr.querySelector('[data-link-actions="1"]');
      if (actions && link) {
        const copyBtn = actions.querySelector('button[data-action="copy-link"]');
        const openBtn = actions.querySelector('button[data-action="open-link"]');
        copyBtn?.addEventListener("click", async (e) => {
          e.stopPropagation();
          try {
            if (navigator.clipboard?.writeText) {
              await navigator.clipboard.writeText(link);
            } else {
              const ta = document.createElement("textarea");
              ta.value = link;
              document.body.appendChild(ta);
              ta.select();
              document.execCommand("copy");
              document.body.removeChild(ta);
            }
            setStatus(`${lvl}: ссылка скопирована`);
          } catch (err) {
            setStatus("Не удалось скопировать ссылку");
          }
        });
        openBtn?.addEventListener("click", (e) => {
          e.stopPropagation();
          window.open(link, "_blank", "noopener,noreferrer");
        });
      }
      tbody?.appendChild(tr);
    });
  }

  function renderTrafficLightTabs() {
    const wrap = el("trafficLightTabs");
    if (!wrap) return;
    wrap.innerHTML = "";
    const levels = ["Уровень 1","Уровень 2","Уровень 3"];
    const available = levels.filter((lvl) => Array.isArray(state.trafficLightByLevel?.[lvl]) && state.trafficLightByLevel[lvl].length);
    if (!available.length) {
      wrap.style.display = "none";
      return;
    }
    wrap.style.display = "flex";
    if (!state.activeTrafficLevel || !available.includes(state.activeTrafficLevel)) {
      state.activeTrafficLevel = available[0];
    }
    available.forEach((lvl) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "level-tab" + (state.activeTrafficLevel === lvl ? " active" : "");
      btn.textContent = `Светофор ${lvl}`;
      btn.onclick = () => {
        state.activeTrafficLevel = lvl;
        renderTrafficLightTabs();
        renderTrafficLightTable(state.trafficLightByLevel[lvl] || []);
      };
      wrap.appendChild(btn);
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

  function openBotPage(resumeUrl) {
    try {
      const u = String(resumeUrl || "");
      if (!u) return;
      // Separate UI page for bot settings + webhook + auto-reply.
      const target = `/ui/bot?resume_url=${encodeURIComponent(u)}`;
      window.open(target, "_blank", "noopener,noreferrer");
    } catch (e) {
      // ignore
    }
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
      const stageLeft = Math.max(0, Math.ceil(stageEnd - elapsed));
      const totalLeft = Math.max(0, Math.ceil(total - elapsed));
      const ps = el("progressStage");
      const pt = el("progressTimes");
      if (ps) ps.textContent = names[stageIdx] || "";
      if (pt) pt.textContent = `Осталось: этап ~${stageLeft}s, всего ~${totalLeft}s`;
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

  function revokeBlobUrl(u) {
    if (!u) return;
    try { window.URL.revokeObjectURL(u); } catch (e) {}
  }

  function buildExcelUiPayload(trafficLightsByLevel, selectedLevelOverride) {
    return {
      request_text: el("requestText").value.trim(),
      selected_level: selectedLevelOverride || state.selectedLevel,
      queries: state.queries || {},
      queries_with_exclusions: state.queriesWithExclusions || {},
      hh_search_urls: state.hhSearchUrls || {},
      found_counts: state.foundCounts || {},
      candidates_by_level: state.candidatesByLevel || {},
      traffic_lights_by_level: trafficLightsByLevel || null,
    };
  }

  function parseFilenameFromDisposition(cd) {
    try {
      const s = String(cd || "");
      const m = s.match(/filename="([^"]+)"/i);
      return m ? m[1] : "";
    } catch (e) { return ""; }
  }

  async function buildExcelBlob(trafficLightsByLevel, selectedLevelOverride) {
    const body = buildExcelUiPayload(trafficLightsByLevel, selectedLevelOverride);
    if (!body.request_text) throw new Error("Пустой запрос");
    const res = await fetch("/api/export_excel_ui", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const t = await res.text();
      throw new Error(`${res.status}: ${t}`);
    }
    const blob = await res.blob();
    const fn = parseFilenameFromDisposition(res.headers.get("content-disposition")) ||
      `hh_search_${new Date().toISOString().replace(/[-:]/g,"").slice(0,15)}.xlsx`;
    const url = window.URL.createObjectURL(blob);
    return { url, filename: fn };
  }

  function downloadFromUrl(url, filename) {
    if (!url) return;
    const a = document.createElement("a");
    a.href = url;
    a.download = filename || `hh_search_${new Date().toISOString().replace(/[-:]/g,"").slice(0,15)}.xlsx`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  async function ensureFullExcel() {
    const btn = el("btnDownloadFullExcel");
    if (btn) btn.disabled = true;
    const tl = {};
    ["Уровень 1","Уровень 2","Уровень 3"].forEach((lvl) => {
      const items = state.trafficLightByLevel?.[lvl];
      if (Array.isArray(items) && items.length) tl[lvl] = items;
    });
    const out = await buildExcelBlob(Object.keys(tl).length ? tl : null, null);
    revokeBlobUrl(state.fullExcelBlobUrl);
    state.fullExcelBlobUrl = out.url;
    state.fullExcelFileName = out.filename;
    if (btn) btn.disabled = false;
    return out;
  }

  async function ensureLevelExcel(levelName) {
    const cached = state.excelByLevel?.[levelName];
    if (cached?.url) return cached;
    const out = await buildExcelBlob(null, levelName);
    const prev = state.excelByLevel?.[levelName];
    if (prev?.url) revokeBlobUrl(prev.url);
    state.excelByLevel[levelName] = { url: out.url, filename: out.filename };
    return state.excelByLevel[levelName];
  }

  async function ensureTlExcel(levelName) {
    const cached = state.tlExcelByLevel?.[levelName];
    if (cached?.url) return cached;
    const items = state.trafficLightByLevel?.[levelName] || [];
    const tl = (Array.isArray(items) && items.length) ? { [levelName]: items } : null;
    const out = await buildExcelBlob(tl, levelName);
    const prev = state.tlExcelByLevel?.[levelName];
    if (prev?.url) revokeBlobUrl(prev.url);
    state.tlExcelByLevel[levelName] = { url: out.url, filename: out.filename };
    return state.tlExcelByLevel[levelName];
  }

  async function downloadFullExcel() {
    try {
      if (!state.fullExcelBlobUrl) await ensureFullExcel();
      downloadFromUrl(state.fullExcelBlobUrl, state.fullExcelFileName);
      setStatus("Excel скачан.");
    } catch (e) {
      setStatus("Ошибка Excel: " + e.message);
    }
  }

  async function downloadLevelExcel(levelName) {
    try {
      const out = await ensureLevelExcel(levelName);
      downloadFromUrl(out.url, out.filename);
      setStatus("Excel скачан.");
    } catch (e) {
      setStatus("Ошибка Excel: " + e.message);
    }
  }

  async function downloadTrafficExcel(levelName) {
    try {
      const out = await ensureTlExcel(levelName);
      downloadFromUrl(out.url, out.filename);
      setStatus("Excel скачан.");
    } catch (e) {
      setStatus("Ошибка Excel: " + e.message);
    }
  }

  async function downloadExcelSmart(levelName) {
    const items = state.trafficLightByLevel?.[levelName];
    if (Array.isArray(items) && items.length) {
      return await downloadTrafficExcel(levelName);
    }
    return await downloadLevelExcel(levelName);
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

  el("btnOpenBot").onclick = () => {
    try {
      window.open("/ui/bot", "_self", "noopener,noreferrer");
    } catch (e) {
      // ignore
    }
  };

  el("btnBool").onclick = async () => {
    const requestText = el("requestText").value.trim();
    setBusy(true); setStatus("Получаю булевы запросы...");
    try {
      const data = await api("/api/generate_queries", {
        request_text: requestText,
        system_prompt_override: getSystemPromptOverride(),
        user_prompt_override: getUserPromptOverride(),
      });
      if (data.llm_raw) {
        el("llmRaw").textContent = JSON.stringify(data.llm_raw, null, 2);
        el("llmBlock").style.display = "block";
      } else {
        el("llmBlock").style.display = "none";
      }
      renderQueries(data.queries, null);
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
    setBusy(true); setStatus("Поиск: LLM → HH...");
    // Оценка таймингов поиска (без светофора)
    const stage1Sec = 12;
    const stage2Sec = 15;
    const stage3Sec = 5;
    const totalSec = stage1Sec + stage2Sec + stage3Sec;
    const stage1Name = "Этап 1: генерация булевых запросов";
    const stage2Name = "Этап 2: поиск в HH";
    const stage3Name = "Этап 3: постобработка результатов";
    startProgress(stage1Name, stage1Sec, stage2Name, stage2Sec, stage3Name, stage3Sec, totalSec);
    try {
      const data = await api("/api/search", {
        request_text: requestText,
        selected_level: state.selectedLevel,
        candidates_limit: getCandidatesLimit(),
        min_stay_months: getMinStayMonths(),
        allowed_short_jobs: getAllowedShortJobs(),
        jump_mode: getJumpMode(),
        max_not_employed_months: getMaxNotEmployedMonths(),
        svetofor_top_x: getSvetoforTopX(),
        system_prompt_override: getSystemPromptOverride(),
        user_prompt_override: getUserPromptOverride(),
      });
      if (data.llm_raw) {
        el("llmRaw").textContent = JSON.stringify(data.llm_raw, null, 2);
        el("llmBlock").style.display = "block";
      } else {
        el("llmBlock").style.display = "none";
      }
      renderQueries(data.queries, data.hh_search_urls);
      state.candidatesByLevel = data.candidates_by_level;
      state.foundCounts = data.found_counts;
      state.queries = data.queries;
      state.queriesWithExclusions = data.queries_with_exclusions;
      state.hhSearchUrls = data.hh_search_urls;
      state.selectedLevel = pickDefaultLevelByCounts(state.foundCounts, 20);
      state.hasTrafficLightRun = false;
      // reset traffic lights + excel caches
      state.trafficLightByLevel = {};
      state.activeTrafficLevel = null;
      Object.keys(state.excelByLevel || {}).forEach((k) => revokeBlobUrl(state.excelByLevel[k]?.url));
      Object.keys(state.tlExcelByLevel || {}).forEach((k) => revokeBlobUrl(state.tlExcelByLevel[k]?.url));
      state.excelByLevel = {};
      state.tlExcelByLevel = {};
      revokeBlobUrl(state.fullExcelBlobUrl);
      state.fullExcelBlobUrl = null;
      state.fullExcelFileName = "";

      el("results").style.display = "block";
      const levels = ["Уровень 1", "Уровень 2", "Уровень 3"];
      const totalShown = levels.reduce((acc, lvl) => acc + ((state.candidatesByLevel?.[lvl] || []).length), 0);
      el("pickedInfo").textContent = `Показано кандидатов (всего по 3 уровням): ${totalShown}.`;
      renderLevelTabs(state.foundCounts);
      renderActiveLevelTable(state.foundCounts);

      const tlBlock = el("trafficLightBlock");
      if (tlBlock) tlBlock.style.display = "none";
      const tlT = el("tlTbody");
      if (tlT) tlT.innerHTML = "";
      const tlTabs = el("trafficLightTabs");
      if (tlTabs) tlTabs.innerHTML = "";
      const tlBtn = el("btnDownloadTlExcel");
      if (tlBtn) tlBtn.disabled = true;

      // Автосборка полного Excel
      try {
        setStatus("Поиск завершён. Собираю полный Excel...");
        await ensureFullExcel();
        setStatus("Готово.");
      } catch (e) {
        setStatus("Поиск завершён, но полный Excel не собран: " + e.message);
      }

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

  async function runSvetoforForLevel(levelName) {
    const requestText = el("requestText").value.trim();
    const topX = getSvetoforTopX();

    // If already computed for this level - just show via TL tabs (no повторного запуска).
    const existing = state.trafficLightByLevel?.[levelName];
    if (existing && Array.isArray(existing) && existing.length) {
      state.activeTrafficLevel = levelName;
      const tlBlock = el("trafficLightBlock");
      if (tlBlock) tlBlock.style.display = "block";
      renderTrafficLightTabs();
      renderTrafficLightTable(existing);
      const tlBtn = el("btnDownloadTlExcel");
      if (tlBtn) tlBtn.disabled = false;
      state.selectedLevel = levelName;
      state.trafficLightCandidates = [...existing];
      state.hasTrafficLightRun = true;
      return;
    }

    setBusy(true);
    setStatus(`Светофор (${levelName})`);
    try {
      // Оценка тайминга только для светофора (без поиска).
      const stage1Sec = 8;
      const stage2Sec = Math.max(10, Math.ceil(topX / 5) * 8);
      const totalSec = stage1Sec + stage2Sec;
      startProgress("Этап 1: подготовка кандидатов", stage1Sec, `Этап 2: светофор (x${topX})`, stage2Sec, "", 0, totalSec);

      const candidates = (state.candidatesByLevel?.[levelName] || []);
      const data = await api("/api/traffic_light", {
        request_text: requestText,
        selected_level: levelName,
        candidates: candidates,
        min_stay_months: getMinStayMonths(),
        allowed_short_jobs: getAllowedShortJobs(),
        jump_mode: getJumpMode(),
        max_not_employed_months: getMaxNotEmployedMonths(),
        svetofor_top_x: topX,
      });

      const tlItems = data.traffic_light_candidates || [];
      state.trafficLightByLevel[levelName] = tlItems;
      state.selectedLevel = levelName;
      state.hasTrafficLightRun = true;
      state.trafficLightCandidates = [...tlItems];
      // invalidate excel caches
      const prevTl = state.tlExcelByLevel?.[levelName];
      if (prevTl?.url) revokeBlobUrl(prevTl.url);
      state.tlExcelByLevel[levelName] = null;
      revokeBlobUrl(state.fullExcelBlobUrl);
      state.fullExcelBlobUrl = null;
      state.fullExcelFileName = "";

      // show TL section
      state.activeTrafficLevel = levelName;
      const tlBlock = el("trafficLightBlock");
      if (tlBlock) tlBlock.style.display = "block";
      renderTrafficLightTabs();
      renderTrafficLightTable(tlItems);
      const tlBtn = el("btnDownloadTlExcel");
      if (tlBtn) tlBtn.disabled = false;

      // автосборка excel
      try {
        setStatus("Светофор готов. Собираю Excel...");
        await ensureTlExcel(levelName);
        await ensureFullExcel();
        setStatus("Готово.");
      } catch (e) {
        setStatus("Светофор завершён, но Excel не собран: " + e.message);
      }
      stopProgress();
      el("progressStage").textContent = "";
      el("progressTimes").textContent = "";
    } catch (e) {
      stopProgress();
      el("progressStage").textContent = "";
      el("progressTimes").textContent = "";
      setStatus("Ошибка: " + e.message);
    } finally { setBusy(false); }
  }

  el("showPrompt").addEventListener("change", async (e) => {
    const visible = Boolean(e?.target?.checked);
    el("promptBlock").style.display = visible ? "block" : "none";
    if (!visible || state.systemPromptLoaded) return;
    try {
      if (!state.systemPromptLoaded) {
        const systemRes = await fetch("/api/system_prompt");
        const systemTxt = await systemRes.text();
        el("systemPromptText").value = systemTxt;
        state.systemPromptLoaded = true;
      }
      if (!state.userPromptLoaded) {
        const userRes = await fetch("/api/user_prompt");
        const userTxt = await userRes.text();
        el("userPromptText").value = userTxt;
        state.userPromptLoaded = true;
      }
    } catch (err) {
      setStatus("Не удалось загрузить prompt файлы");
    }
  });

  const fullBtn = el("btnDownloadFullExcel");
  if (fullBtn) fullBtn.onclick = () => downloadFullExcel();

  const tlBtn = el("btnDownloadTlExcel");
  if (tlBtn) {
    tlBtn.onclick = () => {
      const lvl = state.activeTrafficLevel || state.selectedLevel || "Уровень 2";
      downloadTrafficExcel(lvl);
    };
  }

</script>
</body>
</html>
"""

