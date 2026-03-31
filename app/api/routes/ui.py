from fastapi import APIRouter
from fastapi.responses import HTMLResponse


router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def index() -> str:
    # Встроенный single-file UI для локальной отладки пайплайна.
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
            <button id="btnSvetofor">Светофор</button>
          </div>
          <div class="row">
            <label class="pill">
              <input type="checkbox" id="exportExcel" />
              Сформировать таблицу Excel
            </label>
            <button class="secondary" id="btnDownloadExcel" type="button" disabled>Скачать Excel</button>
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
        <div class="row" id="levelPick"></div>
        <div class="subtitle" id="pickedInfo"></div>
        <div class="divider"></div>
        <div style="overflow:auto;">
          <table>
            <thead>
              <tr>
                <th>Написать</th>
                <th>Имя/ID</th>
                <th>Позиция</th>
                <th>Локация</th>
                <th>Ссылка</th>
                <th>Возраст</th>
                <th>ЗП</th>
              </tr>
            </thead>
            <tbody id="candTbody"></tbody>
          </table>
        </div>

        <div class="divider"></div>
        <div id="trafficLightBlock" style="display:none;">
          <div class="subtitle">Светофор (ColorScore)</div>
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
    selectedLevel: "Уровень 2",
    systemPromptLoaded: false,
    userPromptLoaded: false,
    trafficLightById: null,
    trafficLightCandidates: [],
    hasTrafficLightRun: false,
    excelBlobUrl: null,
    excelFileName: "",
  };

  function setStatus(text) { el("status").textContent = text || ""; }
  function setBusy(b) {
    el("btnDefault").disabled = b;
    el("btnBool").disabled = b;
    el("btnSearch").disabled = b;
    const tlBtn = el("btnSvetofor");
    if (tlBtn) tlBtn.disabled = b;
    const candT = el("candLimit");
    if (candT) candT.disabled = b;
    const extraIds = [
      "svetoforTopX",
      "minStayMonths",
      "allowedShortJobs",
      "jumpMode",
      "maxNotEmployedMonths",
      "exportExcel",
      "btnDownloadExcel",
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
    const tbody = el("tlTbody");
    state.trafficLightById = {};
    tbody.innerHTML = "";

    const list = Array.isArray(items) ? items : [];
    state.trafficLightCandidates = [...list];
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

  function renderQueries(queries) {
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
    renderQueryLinks(queries);
  }

  function buildHhSearchUrl(query) {
    const params = new URLSearchParams({
      text: query || "",
      logic: "normal",
      pos: "full_text",
      exp_period: "all_time",
      exp_company_size: "any",
      filter_exp_period: "all_time",
      relocation: "living_or_relocation",
      title: query || "",
      age_from: "",
      age_to: "45",
      employment: "full",
      gender: "unknown",
      salary_from: "",
      salary_to: "",
      currency_code: "RUR",
      order_by: "relevance",
      search_period: "0",
      items_on_page: "50",
      hhtmFrom: "resume_search_form",
    });
    ["unknown", "active_search", "looking_for_offers"].forEach((v) => params.append("job_search_status", v));
    ["between3And6", "moreThan6"].forEach((v) => params.append("experience", v));
    params.append("area", "113");
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

  function renderQueryLinks(queries) {
    const wrap = el("queryLinks");
    wrap.innerHTML = "";
    ["Уровень 1","Уровень 2","Уровень 3"].forEach((lvl) => {
      const href = buildHhSearchUrl(queries[lvl] || "");
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

  function renderLevelPicker(foundCounts) {
    const wrap = el("levelPick");
    wrap.innerHTML = "";
    ["Уровень 1","Уровень 2","Уровень 3"].forEach((lvl) => {
      const rawCount = foundCounts?.[lvl];
      const parsed = Number(rawCount);
      const listLen = (state.candidatesByLevel?.[lvl] || []).length;
      const count = Number.isFinite(parsed) && parsed > 0 ? parsed : listLen;
      const btn = document.createElement("button");
      btn.className = "secondary";
      btn.textContent = `${lvl} — найдено: ${count}`;
      btn.onclick = () => { state.selectedLevel = lvl; renderCandidates(); };
      wrap.appendChild(btn);
    });
  }

  function renderCandidates() {
    const lvl = state.selectedLevel;
    const list = (state.candidatesByLevel?.[lvl] || []);
    el("pickedInfo").textContent = `Выбран: ${lvl}. Показано кандидатов: ${list.length}`;

    const tbody = el("candTbody");
    tbody.innerHTML = "";
    list.forEach((c) => {
      const area = c.area?.name || c.area?.id || "";
      const link = c.alternate_url || c.url || "";
      const salary = c.salary?.amount ? `${c.salary.amount} ${c.salary.currency||""}` : (c.salary ? JSON.stringify(c.salary) : "");
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
            Написать
          </button>
        </td>
        <td class="mono">${escapeHtml(c.first_name || c.last_name ? ((c.last_name||"") + " " + (c.first_name||"")).trim() : (c.id||""))}</td>
        <td>${escapeHtml(c.title || "")}</td>
        <td>${escapeHtml(area)}</td>
        <td>${link ? `<a href="${encodeURI(link)}" target="_blank" rel="noreferrer">${escapeHtml(link)}</a>` : ""}</td>
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
      tbody.appendChild(tr);
    });
  }

  function pickBestLevelByCandidates() {
    const has = (lvl) => (state.candidatesByLevel?.[lvl] || []).length > 0;
    if (has("Уровень 3")) return "Уровень 3";
    if (has("Уровень 2")) return "Уровень 2";
    if (has("Уровень 1")) return "Уровень 1";
    return state.selectedLevel || "Уровень 2";
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

  function revokeExcelBlobUrl() {
    if (state.excelBlobUrl) {
      try { window.URL.revokeObjectURL(state.excelBlobUrl); } catch (e) {}
      state.excelBlobUrl = null;
    }
    state.excelFileName = "";
  }

  function buildExcelPayload() {
    const trafficLightCandidates = Array.isArray(state.trafficLightCandidates) ? state.trafficLightCandidates : [];
    return {
      request_text: el("requestText").value.trim(),
      selected_level: state.selectedLevel,
      candidates_limit: getCandidatesLimit(),
      min_stay_months: getMinStayMonths(),
      allowed_short_jobs: getAllowedShortJobs(),
      jump_mode: getJumpMode(),
      max_not_employed_months: getMaxNotEmployedMonths(),
      svetofor_top_x: getSvetoforTopX(),
      include_traffic_light: !!state.hasTrafficLightRun,
      traffic_light_candidates_for_excel: trafficLightCandidates,
      system_prompt_override: getSystemPromptOverride(),
      user_prompt_override: getUserPromptOverride(),
    };
  }

  async function prebuildExcel() {
    const exportEnabled = !!el("exportExcel")?.checked;
    const btnXls = el("btnDownloadExcel");
    if (!exportEnabled) {
      revokeExcelBlobUrl();
      if (btnXls) btnXls.disabled = true;
      return;
    }
    const hasResults = Boolean(state.candidatesByLevel);
    if (!hasResults) {
      if (btnXls) btnXls.disabled = true;
      return;
    }
    const body = buildExcelPayload();
    if (!body.request_text) {
      if (btnXls) btnXls.disabled = true;
      return;
    }
    if (btnXls) btnXls.disabled = true;
    setStatus("Формирую Excel заранее...");
    const res = await fetch("/api/export_excel", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const t = await res.text();
      throw new Error(`${res.status}: ${t}`);
    }
    const blob = await res.blob();
    revokeExcelBlobUrl();
    state.excelBlobUrl = window.URL.createObjectURL(blob);
    state.excelFileName = `hh_search_${new Date().toISOString().replace(/[-:]/g,"").slice(0,15)}.xlsx`;
    if (btnXls) btnXls.disabled = false;
    setStatus("Excel готов. Кнопка «Скачать Excel» скачает сразу.");
  }

  async function downloadExcel() {
    const exportEnabled = !!el("exportExcel")?.checked;
    if (!exportEnabled) {
      setStatus("Отметьте чекбокс «Сформировать таблицу Excel» перед выгрузкой.");
      return;
    }
    try {
      if (!state.excelBlobUrl) {
        await prebuildExcel();
      }
      if (!state.excelBlobUrl) {
        throw new Error("Excel еще не готов");
      }
      const a = document.createElement("a");
      a.href = state.excelBlobUrl;
      a.download = state.excelFileName || `hh_search_${new Date().toISOString().replace(/[-:]/g,"").slice(0,15)}.xlsx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setStatus("Excel скачан.");
    } catch (e) {
      setStatus("Ошибка Excel: " + e.message);
    }
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
      renderQueries(data.queries);
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
      renderQueries(data.queries);
      state.candidatesByLevel = data.candidates_by_level;
      state.foundCounts = data.found_counts;
      state.selectedLevel = pickBestLevelByCandidates();
      state.hasTrafficLightRun = false;
      revokeExcelBlobUrl();

      renderLevelPicker(state.foundCounts);
      el("results").style.display = "block";
      renderCandidates();
      renderTrafficLightTable([]);

      if (el("exportExcel")?.checked) {
        try {
          await prebuildExcel();
        } catch (e) {
          setStatus("Поиск завершён, но Excel не собран: " + e.message);
        }
      } else {
        const btnXls = el("btnDownloadExcel");
        if (btnXls) btnXls.disabled = true;
      }

      stopProgress();
      el("progressStage").textContent = "";
      el("progressTimes").textContent = "";
      setStatus("Готово.");
    } catch (e) {
      stopProgress();
      el("progressStage").textContent = "";
      el("progressTimes").textContent = "";
      setStatus("Ошибка: " + e.message);
    } finally { setBusy(false); }
  };

  el("btnSvetofor").onclick = async () => {
    const requestText = el("requestText").value.trim();
    const topX = getSvetoforTopX();
    setBusy(true);
    setStatus("Светофор: LLM → HH → LLM...");
    try {
      // Ориентировочная оценка таймингов (без стриминга), чтобы пользователь видел прогресс.
      const stage1Sec = 20;
      const stage2Sec = 25;
      const stage3Sec = Math.max(10, Math.ceil(topX / 5) * 8);
      const totalSec = stage1Sec + stage2Sec + stage3Sec;
      const stage1Name = "Этап 1: генерация булевых запросов";
      const stage2Name = "Этап 2: поиск в HH";
      const stage3Name = `Этап 3: светофор (x${topX})`;
      startProgress(stage1Name, stage1Sec, stage2Name, stage2Sec, stage3Name, stage3Sec, totalSec);

      const data = await api("/api/svetofor", {
        request_text: requestText,
        selected_level: state.selectedLevel,
        candidates_limit: getCandidatesLimit(),
        min_stay_months: getMinStayMonths(),
        allowed_short_jobs: getAllowedShortJobs(),
        jump_mode: getJumpMode(),
        max_not_employed_months: getMaxNotEmployedMonths(),
        svetofor_top_x: topX,
        system_prompt_override: getSystemPromptOverride(),
        user_prompt_override: getUserPromptOverride(),
      });
      if (data.llm_raw) {
        el("llmRaw").textContent = JSON.stringify(data.llm_raw, null, 2);
        el("llmBlock").style.display = "block";
      } else {
        el("llmBlock").style.display = "none";
      }

      renderQueries(data.queries);
      state.candidatesByLevel = data.candidates_by_level;
      state.foundCounts = data.found_counts;
      state.selectedLevel = pickBestLevelByCandidates();
      state.hasTrafficLightRun = true;
      revokeExcelBlobUrl();

      renderLevelPicker(state.foundCounts);
      el("results").style.display = "block";
      renderCandidates();

      renderTrafficLightTable(data.traffic_light_candidates || []);
      if (el("exportExcel")?.checked) {
        try {
          await prebuildExcel();
        } catch (e) {
          setStatus("Светофор завершён, но Excel не собран: " + e.message);
        }
      } else {
        const btnXls = el("btnDownloadExcel");
        if (btnXls) btnXls.disabled = true;
      }
      stopProgress();
      el("progressStage").textContent = "";
      el("progressTimes").textContent = "";
      setStatus("Готово.");
    } catch (e) {
      stopProgress();
      el("progressStage").textContent = "";
      el("progressTimes").textContent = "";
      setStatus("Ошибка: " + e.message);
    } finally { setBusy(false); }
  };

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

  const btnX = el("btnDownloadExcel");
  if (btnX) {
    btnX.onclick = () => { downloadExcel(); };
  }
  const exportCb = el("exportExcel");
  if (exportCb) {
    exportCb.onchange = async () => {
      if (!exportCb.checked) {
        revokeExcelBlobUrl();
        const btnXls = el("btnDownloadExcel");
        if (btnXls) btnXls.disabled = true;
        return;
      }
      if (!state.candidatesByLevel) {
        const btnXls = el("btnDownloadExcel");
        if (btnXls) btnXls.disabled = true;
        return;
      }
      try {
        await prebuildExcel();
      } catch (e) {
        setStatus("Ошибка Excel: " + e.message);
      }
    };
  }

</script>
</body>
</html>
"""

