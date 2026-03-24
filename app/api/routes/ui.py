from fastapi import APIRouter
from fastapi.responses import HTMLResponse


router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def index() -> str:
    # Single-file UI for easy debugging.
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
        <div class="title">поиск резюме (LLM → булевы → HH)</div>
      </div>

      <textarea id="requestText" placeholder="Вставьте запрос/требования..."></textarea>

      <div class="row">
        <button class="secondary" id="btnDefault">Запрос по умолчанию</button>
        <button class="secondary" id="btnBool">Получить булевый запрос</button>
        <button id="btnSearch">Поиск</button>
        <label class="pill"><input type="checkbox" id="showPrompt" /> показать промпт</label>
      </div>

      <div id="status" class="subtitle"></div>
      <div id="tokenInfo" class="subtitle" style="color:#000;">Ключ: SSP SOFT (по умолчанию)</div>

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
  };

  function setStatus(text) { el("status").textContent = text || ""; }
  function setBusy(b) {
    el("btnDefault").disabled = b;
    el("btnBool").disabled = b;
    el("btnSearch").disabled = b;
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
        <td class="mono">${escapeHtml(c.first_name || c.last_name ? ((c.last_name||"") + " " + (c.first_name||"")).trim() : (c.id||""))}</td>
        <td>${escapeHtml(c.title || "")}</td>
        <td>${escapeHtml(area)}</td>
        <td>${link ? `<a href="${encodeURI(link)}" target="_blank" rel="noreferrer">${escapeHtml(link)}</a>` : ""}</td>
        <td>${c.age ?? ""}</td>
        <td class="mono">${escapeHtml(salary || "")}</td>
      `;
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
      setStatus("Готово.");
    } catch (e) {
      setStatus("Ошибка: " + e.message);
    } finally { setBusy(false); }
  };

  el("btnSearch").onclick = async () => {
    const requestText = el("requestText").value.trim();
    setBusy(true); setStatus("Поиск: LLM → HH...");
    try {
      const data = await api("/api/search", {
        request_text: requestText,
        selected_level: state.selectedLevel,
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

      renderLevelPicker(state.foundCounts);
      el("results").style.display = "block";
      renderCandidates();

      setStatus("Готово.");
    } catch (e) {
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

</script>
</body>
</html>
"""

