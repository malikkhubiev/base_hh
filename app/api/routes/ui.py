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

      <textarea id="requestText" placeholder="Вставьте запрос/требования..."></textarea>
      <textarea id="generalReqText" class="prompt-editor" placeholder="Общие требования (для Скрининга)..." style="min-height:120px;"></textarea>

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
              Минимум кандидатов
              <input type="number" id="candLimit" value="20" min="1" max="200" />
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
        <div class="grid3" style="grid-template-columns: 1fr 1fr; gap:12px;">
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
          <div class="card">
            <div class="label">Общие требования (true/false)</div>
            <div style="overflow:auto; margin-top:8px;">
              <table>
                <thead>
                  <tr>
                    <th>OK</th>
                    <th>Проверка</th>
                    <th>Доказательство</th>
                  </tr>
                </thead>
                <tbody id="tlModalChecksTbody"></tbody>
              </table>
            </div>
          </div>
        </div>
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
    finalBooleanQuery: "",
    stageAttempts: [],
    totalIterations: 0,
    promptRestarts: 0,
    selectedCandidateIds: new Set(),
    screeningById: {},
  };

  function setStatus(text) { el("status").textContent = text || ""; }
  function setBusy(b) {
    el("btnDefault").disabled = b;
    el("btnBool").disabled = b;
    el("btnSearch").disabled = b;
    const candT = el("candLimit");
    if (candT) candT.disabled = b;
    const extraIds = ["btnScreening"];
    extraIds.forEach((id) => {
      const t = el(id);
      if (t) t.disabled = b;
    });
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

  // svetofor_top_x removed: screening runs on selected candidates.

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
    if (titleEl) titleEl.textContent = "Светофор (ColorScore) + Общие требования";

    list.forEach((c) => {
      const id = String(c.id ?? "");
      const score = Number(c.color_score_percent ?? 0);
      const checks = state.screeningById?.[id]?.checks;
      const checksList = Array.isArray(checks) ? checks : [];
      const totalChecks = checksList.length;
      const okChecks = checksList.filter((x) => !!x?.ok).length;
      const checksOk = totalChecks > 0 && okChecks === totalChecks;
      const rectBg = tlColorForScore(score);
      const circleBorder = score >= 60 ? "#0b8a3a" : (score >= 40 ? "#d9b000" : "#ff4d4d");
      const checksBorder = checksOk ? "#0b8a3a" : "#ff4d4d";
      const checksBg = checksOk ? "#ddf8e7" : "rgba(255,120,117,.3)";
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
            <div class="tl-rect" style="background:${totalChecks ? checksBg : "#fff"}; border-color:${totalChecks ? checksBorder : "#000"};" title="Общие требования (true/total)">
              <div class="mono" style="font-size:14px; line-height:1;">${totalChecks ? `${okChecks}/${totalChecks}` : "-"}</div>
            </div>
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
      state.trafficLightById[id] = c;
      tbody.appendChild(tr);
    });
  }

  function renderTrafficLightTableInto(levelName, items) {
    const idx = String(levelName || "main").toLowerCase().replace(/[^a-zа-я0-9]+/gi, "-");
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

    const candidateId = String(c?.id ?? "");
    const checks = state.screeningById?.[candidateId]?.checks;
    const checksList = Array.isArray(checks) ? checks : null;
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

    // Render "Общие требования" рядом (если есть checks).
    const checksTbody = el("tlModalChecksTbody");
    if (checksTbody) {
      checksTbody.innerHTML = "";
      const list = checksList || [];
      list.forEach((it) => {
        const ok = !!it?.ok;
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td class="mono" style="font-weight:800; color:${ok ? "#0b8a3a" : "#ff4d4d"};">${ok ? "TRUE" : "FALSE"}</td>
          <td>${escapeHtml(it?.requirement ?? "")}</td>
          <td>${escapeHtml(it?.evidence ?? "")}</td>
        `;
        checksTbody.appendChild(tr);
      });
    }

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
    const q = state.finalBooleanQuery || "";
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
      const result = enough ? "Хватило" : "Меньше нужного";
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

    const maxJobs = (list || []).reduce((m, c) => {
      const exp = c?.experience_full ?? c?.experienceFull;
      const n = Array.isArray(exp) ? exp.length : 0;
      return Math.max(m, n);
    }, 0);
    const expHeaders = Array.from({ length: maxJobs }, (_, i) => `<th>Опыт #${i + 1}</th>`).join("");

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
                <th>Ссылка</th>
                <th>Возраст</th>
                <th>ЗП</th>
                ${expHeaders}
              </tr>
            </thead>
            <tbody id="tbody-level-${escapeHtml(idx)}"></tbody>
          </table>
        </div>
        <div class="row" style="justify-content:flex-end; margin-top:12px;">
          <button id="btnScreening" type="button" disabled>Скрининг</button>
        </div>
      </div>
    `;

    const tbody = host.querySelector(`#tbody-level-${idx}`);
    (list || []).forEach((c) => {
      const area = c.area?.name || c.area?.id || "";
      const link = c.alternate_url || c.url || "";
      const salary = c.salary?.amount ? `${c.salary.amount} ${c.salary.currency||""}` : (c.salary ? JSON.stringify(c.salary) : "");
      const fullName = (c.first_name || c.last_name)
        ? ((c.last_name||"") + " " + (c.first_name||"")).trim()
        : "-";
      const nameShort = truncateEnd(fullName, 25);
      const cid = String(c.id || "");
      const fullExp = Array.isArray(c?.experience_full) ? c.experience_full : [];
      const expCells = Array.from({ length: maxJobs }, (_, j) => {
        const it = fullExp[j] || null;
        if (!it) return `<td></td>`;
        const start = it?.start || "";
        const end = it?.end || "";
        const period = `${start}${(start && end) ? " — " : ""}${end}`.trim();
        const company = it?.company || "";
        const position = it?.position || "";
        const areaName = it?.area?.name || it?.area?.id || "";
        const industries = Array.isArray(it?.industries) ? it.industries : [];
        const industriesText = industries.map((x) => x?.name).filter(Boolean).join(", ");
        const text = [period, company, position, areaName, industriesText].filter(Boolean).join(" | ");
        return `<td class="mono">${escapeHtml(text)}</td>`;
      }).join("");
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>
          <input type="checkbox" data-select="1" ${state.selectedCandidateIds.has(cid) ? "checked" : ""} ${cid ? "" : "disabled"} />
        </td>
        <td class="mono" title="${escapeHtml(fullName)}">${escapeHtml(nameShort)}</td>
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
        ${expCells}
      `;
      const chk = tr.querySelector('input[data-select="1"]');
      if (chk) {
        chk.onchange = () => {
          if (!cid) return;
          if (chk.checked) state.selectedCandidateIds.add(cid);
          else state.selectedCandidateIds.delete(cid);
          const btn = el("btnScreening");
          if (btn) btn.disabled = state.selectedCandidateIds.size <= 0;
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
            setStatus(`Ссылка скопирована`);
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

    const btn = el("btnScreening");
    if (btn) {
      btn.disabled = state.selectedCandidateIds.size <= 0;
      btn.onclick = async () => {
        await runScreeningForSelected();
      };
    }
  }

  async function runScreeningForSelected() {
    const requestText = el("requestText").value.trim();
    const generalReqText = el("generalReqText").value.trim();
    const list = Array.isArray(state.candidates) ? state.candidates : [];
    const selected = list.filter((c) => state.selectedCandidateIds.has(String(c.id || "")));
    if (!selected.length) {
      setStatus("Выберите кандидатов для скрининга");
      return;
    }
    setBusy(true);
    setStatus(`Скрининг: ${selected.length} кандидатов...`);
    try {
      const data = await api("/api/screening", {
        request_text: requestText,
        general_requirements_text: generalReqText,
        candidates: selected,
      });
      const tlItems = Array.isArray(data.traffic_light_candidates) ? data.traffic_light_candidates : [];
      const gr = Array.isArray(data.general_requirements) ? data.general_requirements : [];
      state.screeningById = {};
      gr.forEach((it) => {
        const cid = String(it?.id ?? "");
        if (!cid) return;
        state.screeningById[cid] = it;
      });
      renderTrafficLightTable(tlItems);
      const tlBlock = el("trafficLightBlock");
      if (tlBlock) tlBlock.style.display = "block";
      setStatus("Готово.");
    } catch (e) {
      setStatus("Ошибка: " + e.message);
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
      state.totalIterations = 0;
      state.promptRestarts = 0;
      const data = await api("/api/search", {
        request_text: requestText,
        candidates_limit: getCandidatesLimit(),
      });
      renderQueries(data.query, data.final_search_url);
      const candidates = Array.isArray(data.candidates) ? data.candidates : [];
      state.candidates = candidates;
      state.foundCount = Number(data.found_count || 0);
      state.query = data.query || "";
      state.startedAt = data.started_at || null;
      state.boolFinishedAt = data.bool_finished_at || null;
      state.hhFinishedAt = data.hh_finished_at || null;
      state.finishedAt = data.finished_at || null;
      state.finalBooleanQuery = data.final_boolean_query || "";
      state.stageAttempts = data.stage_attempts || [];
      state.totalIterations = Number(data.total_iterations || 0);
      state.promptRestarts = Number(data.prompt_restarts || 0);
      // reset traffic lights
      state.screeningById = {};

      el("results").style.display = "block";
      const totalShown = candidates.length;
      const minN = getCandidatesLimit();
      el("pickedInfo").textContent = `Минимум: ${minN}. Показано кандидатов: ${totalShown} (макс: ${Math.min(200, minN * 3)}).`;
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

