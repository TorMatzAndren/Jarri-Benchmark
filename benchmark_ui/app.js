const state = {
  modelRankings: [],
  taskRankings: [],
  modelTaskTdp: [],
  taskRegistry: [],
  failureSurfaces: [],
  pareto: null,
  dataIndex: null,
  loadedJsonCache: {},
  selectedModelName: null,
  selectedTaskId: null,
  selectedFamily: "all",
  browserTab: "duckdb",
  selectedPath: null,
  sortKey: "avg_score_percent",
  sortDirection: "desc",
  modelSearch: "",
  taskSearch: "",
  focusSelectedPairOnly: false,
};

const HELP_TEXT = {
  model: "Model identifier as recorded in the benchmark ledger and exported from DuckDB.",
  fully_correct_rate: "Fraction of runs that were completely correct under the evaluator. Higher is better.",
  pipeline_usable_rate: "Fraction of runs that produced output usable in a deterministic downstream pipeline, even if not fully correct.",
  usable_output_rate: "Fraction of runs that produced a usable artifact at all. This is looser than full correctness.",
  hard_failure_rate: "Fraction of runs that failed badly, such as parse failure, runtime failure, or structurally unusable output. Lower is better.",
  avg_score_percent: "Average evaluator score percentage across the slice. Higher is better.",
  avg_energy_j: "Average observed energy used by the slice, in joules. Lower is better.",
  avg_tokens_per_second: "Average token generation speed. Higher is faster.",
  avg_output_tokens: "Average output tokens produced per task. Lower usually means less token waste.",
  avg_total_tokens: "Average total tokens per task, including prompt and output.",
  avg_joules_per_output_token: "Average joules spent per output token. Lower is better.",
  avg_output_tokens_per_joule: "Average output tokens produced per joule. Higher is better.",
  avg_score_per_100_output_tokens: "Average score gained per 100 output tokens. Higher is better.",
  avg_score_per_output_token: "Average score gained per output token. Higher is better.",
  avg_score_per_wh_strict: "Average evaluator score per watt-hour. Higher is better.",
  outtok_vs_best: "Relative output-token consumption compared with the most token-efficient currently visible row set. 1.00x is best. Higher values mean more token waste.",
  scorewh_vs_best: "Relative score-per-Wh compared with the strongest currently visible row set. 1.00x is best.",
  fully_correct_per_joule: "Fully-correct rate divided by average energy. Higher is better.",
  pipeline_usable_per_joule: "Pipeline-usable rate divided by average energy. Higher is better.",
  tdp_level: "GPU power limit level used during the run slice.",
  gpu_name: "GPU name observed for the slice.",
  runtime_residency_status: "Whether the model was fully resident in GPU or fell back into hybrid CPU/GPU mode.",
  canonical_runtime: "Canonical runtime policy interpretation for the slice.",
  benchmark_count: "Number of benchmark runs behind this aggregated row.",
  pareto: "A Pareto frontier keeps only tradeoffs that are not clearly worse on both correctness and energy at the same time.",
  failure_record_count: "Total emitted failure-surface records for this model × task slice.",
  failure_signal_density: "Average number of emitted failure signals per benchmark run.",
  runs_with_failure_signals: "Count of runs that emitted at least one non-success failure signal.",
  runs_with_failure_signals_rate: "Fraction of benchmark runs that emitted at least one non-success failure signal.",
};

function safeNum(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function percent(value) {
  return `${(safeNum(value) * 100).toFixed(2)}%`;
}

function energy(value) {
  return `${safeNum(value).toFixed(2)} J`;
}

function number2(value) {
  return safeNum(value).toFixed(2);
}

function number6(value) {
  return safeNum(value).toFixed(6);
}

function ratio2(value) {
  return `${safeNum(value).toFixed(2)}x`;
}

function uniqueSorted(values) {
  return Array.from(new Set(values.filter(Boolean))).sort((a, b) => String(a).localeCompare(String(b)));
}

function sum(values) {
  return values.reduce((acc, v) => acc + safeNum(v), 0);
}

function avg(values) {
  if (!values.length) return 0;
  return sum(values) / values.length;
}

function compareValues(a, b) {
  if (a === null || a === undefined) return 1;
  if (b === null || b === undefined) return -1;
  if (a < b) return -1;
  if (a > b) return 1;
  return 0;
}

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function infoDot(key) {
  const body = HELP_TEXT[key] || key;
  return `<span class="info-dot help-anchor" data-help-title="${esc(key)}" data-help-body="${esc(body)}">i</span>`;
}

function statLabel(label, key) {
  return `
    <div class="stat-label">
      ${esc(label)}
      ${infoDot(key)}
    </div>
  `;
}

function thLabel(label, key) {
  return `
    <span style="display:inline-flex;align-items:center;gap:6px;">
      <span>${esc(label)}</span>
      ${infoDot(key)}
    </span>
  `;
}

function buildStat(label, value, key, extraClass = "") {
  return `
    <div class="stat">
      ${statLabel(label, key)}
      <div class="stat-value ${extraClass}">${value}</div>
    </div>
  `;
}

function cssClassForRate(value) {
  const v = safeNum(value);
  if (v >= 0.5) return "good";
  if (v >= 0.1) return "warn";
  return "bad";
}

function cssClassForInverseRate(value) {
  const v = safeNum(value);
  if (v <= 0.1) return "good";
  if (v <= 0.4) return "warn";
  return "bad";
}

function cssClassForRelativeLow(value) {
  const v = safeNum(value, 1);
  if (v <= 1.25) return "good";
  if (v <= 2.0) return "warn";
  return "bad";
}

function cssClassForRelativeHigh(value) {
  const v = safeNum(value, 0);
  if (v >= 0.75) return "good";
  if (v >= 0.35) return "warn";
  return "bad";
}

function makeScale(values, { higherIsBetter = true } = {}) {
  const valid = values
    .map(v => safeNum(v, NaN))
    .filter(v => Number.isFinite(v));

  if (!valid.length) {
    return { min: 0, max: 0, higherIsBetter };
  }

  return {
    min: Math.min(...valid),
    max: Math.max(...valid),
    higherIsBetter,
  };
}

function cssClassFromScale(value, scale) {
  if (!scale) return "";
  const v = safeNum(value, NaN);
  if (!Number.isFinite(v)) return "";

  if (scale.max === scale.min) return "good";

  const normalized = (v - scale.min) / (scale.max - scale.min);
  const score = scale.higherIsBetter ? normalized : 1 - normalized;

  if (score >= 0.67) return "good";
  if (score >= 0.34) return "warn";
  return "bad";
}

async function loadJson(path) {
  if (state.loadedJsonCache[path]) return state.loadedJsonCache[path];
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`Failed to load ${path}: HTTP ${response.status}`);
  const data = await response.json();
  state.loadedJsonCache[path] = data;
  return data;
}

async function loadModelRankings() {
  return loadJson("./data/duckdb_model_rankings.json");
}

async function loadTaskRankings() {
  return loadJson("./data/duckdb_task_rankings.json");
}

async function loadModelTaskTdp() {
  return loadJson("./data/duckdb_model_task_tdp.json");
}

async function loadTaskRegistry() {
  return loadJson("./data/duckdb_task_registry.json");
}

async function loadFailureSurfaces() {
  return loadJson("./data/duckdb_failure_surfaces.json");
}

async function loadPareto() {
  return loadJson("./data/duckdb_pareto_frontiers.json");
}

async function loadDataIndex() {
  try {
    return await loadJson("./data/data_index.json");
  } catch {
    return null;
  }
}

function enrichModelRows(rows) {
  const validOutTok = rows
    .map(row => safeNum(row.avg_output_tokens, NaN))
    .filter(value => Number.isFinite(value) && value > 0);

  const validScoreWh = rows
    .map(row => safeNum(row.avg_score_per_wh_strict, NaN))
    .filter(value => Number.isFinite(value) && value > 0);

  const bestOutTok = validOutTok.length ? Math.min(...validOutTok) : null;
  const bestScoreWh = validScoreWh.length ? Math.max(...validScoreWh) : null;

  return rows.map(row => ({
    ...row,
    benchmark_count: row.rows,
    outtok_vs_best: bestOutTok && safeNum(row.avg_output_tokens, 0) > 0
      ? safeNum(row.avg_output_tokens) / bestOutTok
      : null,
    scorewh_vs_best: bestScoreWh && safeNum(row.avg_score_per_wh_strict, 0) > 0
      ? safeNum(row.avg_score_per_wh_strict) / bestScoreWh
      : null,
  }));
}

function enrichTaskRows(rows) {
  const validOutTok = rows
    .map(row => safeNum(row.avg_output_tokens, NaN))
    .filter(value => Number.isFinite(value) && value > 0);

  const validScoreWh = rows
    .map(row => safeNum(row.avg_score_per_wh_strict, NaN))
    .filter(value => Number.isFinite(value) && value > 0);

  const bestOutTok = validOutTok.length ? Math.min(...validOutTok) : null;
  const bestScoreWh = validScoreWh.length ? Math.max(...validScoreWh) : null;

  return rows.map(row => ({
    ...row,
    outtok_vs_best: bestOutTok && safeNum(row.avg_output_tokens, 0) > 0
      ? safeNum(row.avg_output_tokens) / bestOutTok
      : null,
    scorewh_vs_best: bestScoreWh && safeNum(row.avg_score_per_wh_strict, 0) > 0
      ? safeNum(row.avg_score_per_wh_strict) / bestScoreWh
      : null,
  }));
}

function getModelRows() {
  let rows = enrichModelRows([...state.modelRankings]);

  if (state.modelSearch.trim()) {
    const q = state.modelSearch.trim().toLowerCase();
    rows = rows.filter(r => String(r.model).toLowerCase().includes(q));
  }

  return rows;
}

function getVisibleTaskRows() {
  let rows = enrichTaskRows([...state.taskRankings]);

  if (state.selectedFamily !== "all") {
    rows = rows.filter(r => r.task_family === state.selectedFamily);
  }

  if (state.taskSearch.trim()) {
    const q = state.taskSearch.trim().toLowerCase();
    rows = rows.filter(r =>
      String(r.task_id || "").toLowerCase().includes(q) ||
      String(r.model || "").toLowerCase().includes(q) ||
      String(r.task_family || "").toLowerCase().includes(q)
    );
  }

  return rows;
}

function getAvailableTasks() {
  const rows = state.selectedFamily === "all"
    ? state.modelTaskTdp
    : state.modelTaskTdp.filter(r => r.task_family === state.selectedFamily);

  return uniqueSorted(rows.map(r => r.task_id));
}

function ensureSelectedModelAndTask() {
  const models = uniqueSorted(state.modelRankings.map(r => r.model));
  if (!state.selectedModelName && models.length > 0) {
    state.selectedModelName = models[0];
  }

  if (state.modelSearch.trim()) {
    const q = state.modelSearch.trim().toLowerCase();
    const filteredModels = models.filter(m => m.toLowerCase().includes(q));
    if (filteredModels.length > 0 && !filteredModels.includes(state.selectedModelName)) {
      state.selectedModelName = filteredModels[0];
    }
  }

  const tasks = getAvailableTasks();
  if (!state.selectedTaskId || !tasks.includes(state.selectedTaskId)) {
    state.selectedTaskId = tasks.length > 0 ? tasks[0] : null;
  }
}

function renderOverview(meta) {
  const generated = document.getElementById("generated-at");
  const shape = document.getElementById("dataset-shape");
  if (generated) generated.textContent = `Generated: ${meta}`;
  if (shape) {
    shape.textContent =
      `${state.modelRankings.length} models • ${uniqueSorted(state.modelTaskTdp.map(r => r.task_id)).length} tasks • ${state.modelTaskTdp.length} model-task-TDP rows`;
  }
}

function buildSelectors() {
  ensureSelectedModelAndTask();

  const modelSelector = document.getElementById("model-selector");
  const taskSelector = document.getElementById("task-selector");
  const familySelector = document.getElementById("family-selector");

  const models = uniqueSorted(state.modelRankings.map(r => r.model));
  const visibleModels = state.modelSearch.trim()
    ? models.filter(m => m.toLowerCase().includes(state.modelSearch.trim().toLowerCase()))
    : models;
  const tasks = getAvailableTasks();
  const families = ["all", ...uniqueSorted(state.modelTaskTdp.map(r => r.task_family))];

  if (modelSelector) {
    modelSelector.innerHTML = visibleModels.map(model =>
      `<option value="${esc(model)}" ${model === state.selectedModelName ? "selected" : ""}>${esc(model)}</option>`
    ).join("");
  }

  if (taskSelector) {
    taskSelector.innerHTML = tasks.map(task =>
      `<option value="${esc(task)}" ${task === state.selectedTaskId ? "selected" : ""}>${esc(task)}</option>`
    ).join("");
  }

  if (familySelector) {
    familySelector.innerHTML = families.map(family =>
      `<option value="${esc(family)}" ${family === state.selectedFamily ? "selected" : ""}>${esc(family)}</option>`
    ).join("");
  }
}

function renderModelTable() {
  const root = document.getElementById("model-table");
  if (!root) return;

  const rows = getModelRows();

  rows.sort((a, b) => {
    const cmp = compareValues(a[state.sortKey], b[state.sortKey]);
    return state.sortDirection === "asc" ? cmp : -cmp;
  });

  const scoreScale = makeScale(rows.map(r => r.avg_score_percent), { higherIsBetter: true });
  const energyScale = makeScale(rows.map(r => r.avg_energy_j), { higherIsBetter: false });
  const tpsScale = makeScale(rows.map(r => r.avg_tokens_per_second), { higherIsBetter: true });
  const outTokScale = makeScale(rows.map(r => r.avg_output_tokens), { higherIsBetter: false });
  const score100Scale = makeScale(rows.map(r => r.avg_score_per_100_output_tokens), { higherIsBetter: true });
  const joutScale = makeScale(rows.map(r => r.avg_joules_per_output_token), { higherIsBetter: false });

  root.innerHTML = `
    <table>
      <thead>
        <tr>
          <th data-key="model">${thLabel("Model", "model")}</th>
          <th data-key="rows">${thLabel("n", "benchmark_count")}</th>
          <th data-key="avg_score_percent">${thLabel("Avg Score %", "avg_score_percent")}</th>
          <th data-key="avg_energy_j">${thLabel("Avg Energy J", "avg_energy_j")}</th>
          <th data-key="avg_tokens_per_second">${thLabel("Tokens/s", "avg_tokens_per_second")}</th>
          <th data-key="avg_output_tokens">${thLabel("Out Tokens", "avg_output_tokens")}</th>
          <th data-key="outtok_vs_best">${thLabel("OutTok vs Best", "outtok_vs_best")}</th>
          <th data-key="avg_score_per_100_output_tokens">${thLabel("Score/100tok", "avg_score_per_100_output_tokens")}</th>
          <th data-key="avg_joules_per_output_token">${thLabel("J/OutTok", "avg_joules_per_output_token")}</th>
          <th data-key="scorewh_vs_best">${thLabel("Score/Wh vs Best", "scorewh_vs_best")}</th>
          <th data-key="hard_failure_rate">${thLabel("Hard Failure", "hard_failure_rate")}</th>
          <th data-key="success_rate">${thLabel("Success", "usable_output_rate")}</th>
        </tr>
      </thead>
      <tbody>
        ${rows.map(row => `
          <tr class="model-row ${row.model === state.selectedModelName ? "selected" : ""}" data-model="${esc(row.model)}">
            <td>${esc(row.model)}</td>
            <td>${row.rows ?? "—"}</td>
            <td class="${cssClassFromScale(row.avg_score_percent, scoreScale)}">${number2(row.avg_score_percent)}%</td>
            <td class="${cssClassFromScale(row.avg_energy_j, energyScale)}">${energy(row.avg_energy_j)}</td>
            <td class="${cssClassFromScale(row.avg_tokens_per_second, tpsScale)}">${number2(row.avg_tokens_per_second)}</td>
            <td class="${cssClassFromScale(row.avg_output_tokens, outTokScale)}">${number2(row.avg_output_tokens)}</td>
            <td class="${cssClassForRelativeLow(row.outtok_vs_best)}">${row.outtok_vs_best == null ? "—" : ratio2(row.outtok_vs_best)}</td>
            <td class="${cssClassFromScale(row.avg_score_per_100_output_tokens, score100Scale)}">${number2(row.avg_score_per_100_output_tokens)}</td>
            <td class="${cssClassFromScale(row.avg_joules_per_output_token, joutScale)}">${number2(row.avg_joules_per_output_token)}</td>
            <td class="${cssClassForRelativeHigh(row.scorewh_vs_best)}">${row.scorewh_vs_best == null ? "—" : ratio2(row.scorewh_vs_best)}</td>
            <td class="${cssClassForInverseRate(row.hard_failure_rate)}">${percent(row.hard_failure_rate)}</td>
            <td class="${cssClassForRate(row.success_rate)}">${percent(row.success_rate)}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;

  root.querySelectorAll("th[data-key]").forEach(th => {
    th.onclick = () => {
      const key = th.dataset.key;
      if (state.sortKey === key) {
        state.sortDirection = state.sortDirection === "asc" ? "desc" : "asc";
      } else {
        state.sortKey = key;
        state.sortDirection = key === "model" ? "asc" : "desc";
      }
      renderModelTable();
      bindHelpTooltips();
    };
  });

  root.querySelectorAll(".model-row").forEach(row => {
    row.onclick = () => {
      state.selectedModelName = row.dataset.model;
      ensureSelectedModelAndTask();
      renderAll();
    };
  });
}

function renderSelectedModelDetail() {
  const root = document.getElementById("selected-model-detail");
  if (!root) return;

  const model = getModelRows().find(m => m.model === state.selectedModelName);

  if (!model) {
    root.innerHTML = `<div class="loading">Select a model from the table above.</div>`;
    return;
  }

  const interpretation = `This model currently averages ${number2(model.avg_output_tokens)} output tokens per task at ${number2(model.avg_score_percent)}% score. Its token efficiency is ${number2(model.avg_score_per_100_output_tokens)} score per 100 output tokens, and it uses ${model.outtok_vs_best == null ? "—" : ratio2(model.outtok_vs_best)} the output tokens of the most token-efficient currently visible model.`;
  const energyProfile = `It spends ${number2(model.avg_joules_per_output_token)} joules per output token and delivers ${model.scorewh_vs_best == null ? "—" : ratio2(model.scorewh_vs_best)} of the best currently visible score-per-Wh result.`;

  root.innerHTML = `
    <div class="card">
      <h3>${esc(model.model)}</h3>
      <span class="badge">selected model</span>

      <div class="stats">
        ${buildStat("Benchmarks", model.rows ?? "—", "benchmark_count")}
        ${buildStat("Avg score %", `${number2(model.avg_score_percent)}%`, "avg_score_percent")}
        ${buildStat("Avg energy", energy(model.avg_energy_j), "avg_energy_j")}
        ${buildStat("Tokens/s", number2(model.avg_tokens_per_second), "avg_tokens_per_second")}
        ${buildStat("Out tokens", number2(model.avg_output_tokens), "avg_output_tokens")}
        ${buildStat("Total tokens", number2(model.avg_total_tokens), "avg_total_tokens")}
        ${buildStat("OutTok vs Best", model.outtok_vs_best == null ? "—" : ratio2(model.outtok_vs_best), "outtok_vs_best", cssClassForRelativeLow(model.outtok_vs_best))}
        ${buildStat("Score / 100 tok", number2(model.avg_score_per_100_output_tokens), "avg_score_per_100_output_tokens")}
        ${buildStat("Score / tok", number2(model.avg_score_per_output_token), "avg_score_per_output_token")}
        ${buildStat("J / OutTok", number2(model.avg_joules_per_output_token), "avg_joules_per_output_token")}
        ${buildStat("Tok / joule", number2(model.avg_output_tokens_per_joule), "avg_output_tokens_per_joule")}
        ${buildStat("Score/Wh vs Best", model.scorewh_vs_best == null ? "—" : ratio2(model.scorewh_vs_best), "scorewh_vs_best", cssClassForRelativeHigh(model.scorewh_vs_best))}
        ${buildStat("Hard failure", percent(model.hard_failure_rate), "hard_failure_rate", cssClassForInverseRate(model.hard_failure_rate))}
        ${buildStat("Success", percent(model.success_rate), "usable_output_rate", cssClassForRate(model.success_rate))}
      </div>

      <div class="grid grid-3">
        <div class="card">
          <h3>Interpretation</h3>
          <div class="small">${esc(interpretation)}</div>
        </div>
        <div class="card">
          <h3>Energy profile</h3>
          <div class="small">${esc(energyProfile)}</div>
        </div>
        <div class="card">
          <h3>Coverage</h3>
          <div class="badge">rows: ${model.rows ?? "—"}</div>
          <div class="badge">energy-valid: ${percent(model.energy_valid_rate)}</div>
          <div class="badge">success: ${percent(model.success_rate)}</div>
        </div>
      </div>
    </div>
  `;
}

function renderTaskRegistry() {
  const root = document.getElementById("task-registry-surface");
  if (!root) return;

  const row = state.taskRegistry.find(r => r.task_id === state.selectedTaskId);
  if (!row) {
    root.innerHTML = `<div class="loading">No task registry entry for selected task.</div>`;
    return;
  }

  root.innerHTML = `
    <div class="card">
      <h3>${esc(row.task_title || row.task_id)}</h3>
      <span class="badge">${esc(row.task_id)}</span>
      <span class="badge">${esc(row.task_family || "unknown")}</span>
      ${row.primary_axis ? `<span class="badge">${esc(row.primary_axis)}</span>` : ""}

      <div class="grid grid-2" style="margin-top:16px;">
        <div class="card">
          <h3>Description</h3>
          <div class="task-description small">${esc(row.task_description || "No description available.")}</div>
        </div>
        <div class="card">
          <h3>Success definition</h3>
          <div class="task-description small">${esc(row.success_definition || "No success definition available.")}</div>
        </div>
      </div>

      <div class="grid grid-2" style="margin-top:16px;">
        <div class="card">
          <h3>Prompt preview</h3>
          <div class="task-description small">${esc(row.prompt_preview || row.prompt_first_line || "No prompt preview available.")}</div>
        </div>
        <div class="card">
          <h3>Canonical paths</h3>
          <div class="small">Prompt: ${esc(row.prompt_path || "—")}</div>
          <div class="small" style="margin-top:8px;">Manifest: ${esc(row.manifest_path || "—")}</div>
        </div>
      </div>

      <div class="card" style="margin-top:16px;">
        <h3>Common failure modes</h3>
        <div>
          ${(row.common_failure_modes || []).map(item => `<span class="failure-chip">${esc(item)}</span>`).join("") || '<span class="small">No common failure modes documented.</span>'}
        </div>
      </div>
    </div>
  `;
}

function buildSvgScatterPlot({
  title,
  subtitle,
  rows,
  xKey,
  yKey,
  xLabel,
  yLabel,
  selectedPredicate = () => false,
  frontierPredicate = () => false,
  width = 860,
  height = 360,
}) {
  const validRows = rows.filter(r => Number.isFinite(safeNum(r[xKey], NaN)) && Number.isFinite(safeNum(r[yKey], NaN)));

  if (!validRows.length) {
    return `<div class="loading">No valid chart rows.</div>`;
  }

  const margin = { top: 28, right: 24, bottom: 52, left: 72 };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;

  const xs = validRows.map(r => safeNum(r[xKey]));
  const ys = validRows.map(r => safeNum(r[yKey]));

  let minX = Math.min(...xs);
  let maxX = Math.max(...xs);
  let minY = Math.min(...ys);
  let maxY = Math.max(...ys);

  if (minX === maxX) maxX = minX + 1;
  if (minY === maxY) maxY = minY + 0.01;

  const xPad = (maxX - minX) * 0.08;
  const yPad = (maxY - minY) * 0.10;

  minX = Math.max(0, minX - xPad);
  maxX = maxX + xPad;
  minY = Math.max(0, minY - yPad);
  maxY = maxY + yPad;

  const xScale = (x) => margin.left + ((x - minX) / (maxX - minX)) * innerW;
  const yScale = (y) => margin.top + innerH - ((y - minY) / (maxY - minY)) * innerH;

  const tickCount = 5;
  const xTicks = Array.from({ length: tickCount + 1 }, (_, i) => minX + ((maxX - minX) / tickCount) * i);
  const yTicks = Array.from({ length: tickCount + 1 }, (_, i) => minY + ((maxY - minY) / tickCount) * i);

  const frontierRows = validRows.filter(frontierPredicate).sort((a, b) => safeNum(a[xKey]) - safeNum(b[xKey]));
  const frontierPath = frontierRows.map((r, idx) => {
    const x = xScale(safeNum(r[xKey]));
    const y = yScale(safeNum(r[yKey]));
    return `${idx === 0 ? "M" : "L"} ${x} ${y}`;
  }).join(" ");

  const xGrid = xTicks.map(t => {
    const x = xScale(t);
    return `
      <line x1="${x}" y1="${margin.top}" x2="${x}" y2="${margin.top + innerH}" stroke="rgba(255,255,255,0.08)" />
      <text x="${x}" y="${margin.top + innerH + 18}" fill="#aab4c4" font-size="11" text-anchor="middle">${number2(t)}</text>
    `;
  }).join("");

  const yGrid = yTicks.map(t => {
    const y = yScale(t);
    return `
      <line x1="${margin.left}" y1="${y}" x2="${margin.left + innerW}" y2="${y}" stroke="rgba(255,255,255,0.08)" />
      <text x="${margin.left - 10}" y="${y + 4}" fill="#aab4c4" font-size="11" text-anchor="end">${(safeNum(t) * 100).toFixed(1)}%</text>
    `;
  }).join("");

  const points = validRows.map(r => {
    const x = xScale(safeNum(r[xKey]));
    const y = yScale(safeNum(r[yKey]));
    const selected = selectedPredicate(r);
    const frontier = frontierPredicate(r);

    let fill = "#7fc8ff";
    let stroke = "#cfe7ff";
    let radius = 5;

    if (frontier) {
      fill = "#72da95";
      stroke = "#d7ffe6";
      radius = 6;
    }

    if (selected) {
      fill = "#ffd166";
      stroke = "#fff2c0";
      radius = 7;
    }

    const label = r.model
      ? `${r.model}${r.tdp_level !== undefined && r.tdp_level !== null ? ` @ ${r.tdp_level}` : ""}`
      : (r.task_id || "point");

    const tooltipBody = [
      r.task_id ? `Task: ${r.task_id}` : null,
      r.task_family ? `Family: ${r.task_family}` : null,
      r.tdp_level !== undefined && r.tdp_level !== null ? `TDP: ${r.tdp_level}` : null,
      r.benchmark_count !== undefined ? `Benchmarks: ${r.benchmark_count}` : null,
      `Fully correct: ${percent(r[yKey])}`,
      `Energy: ${number2(r[xKey])} J`,
      r.avg_score_percent !== undefined ? `Avg score: ${number2(r.avg_score_percent)}%` : null,
      r.avg_tokens_per_second !== undefined ? `Tokens/s: ${number2(r.avg_tokens_per_second)}` : null,
      r.gpu_name ? `GPU: ${r.gpu_name}` : null
    ].filter(Boolean);

    const visibleLabel = selected
      ? `<text x="${x + 8}" y="${y - 8}" class="chart-label">${esc(label)}</text>`
      : "";

    return `
      <g>
        <circle
          class="chart-point"
          cx="${x}"
          cy="${y}"
          r="${radius}"
          fill="${fill}"
          stroke="${stroke}"
          stroke-width="1.5"
          data-tt-title="${esc(label)}"
          data-tt-body="${esc(tooltipBody.join("||"))}"
        ></circle>
        ${visibleLabel}
      </g>
    `;
  }).join("");

  return `
    <div class="card">
      <h3>${esc(title)} ${infoDot("pareto")}</h3>
      <p class="small">${esc(subtitle)}</p>
      <div class="small" style="margin-bottom:10px;">
        Each point is one <strong>model × TDP slice</strong>. Left is lower energy. Higher is more fully correct.
      </div>
      <div class="scroll-x">
        <svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg" role="img">
          <rect x="0" y="0" width="${width}" height="${height}" fill="transparent"></rect>
          ${xGrid}
          ${yGrid}
          <line x1="${margin.left}" y1="${margin.top + innerH}" x2="${margin.left + innerW}" y2="${margin.top + innerH}" stroke="#c9d6f0" stroke-width="1.5" />
          <line x1="${margin.left}" y1="${margin.top}" x2="${margin.left}" y2="${margin.top + innerH}" stroke="#c9d6f0" stroke-width="1.5" />
          ${frontierPath ? `<path d="${frontierPath}" fill="none" stroke="#72da95" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" />` : ""}
          ${points}
          <text x="${margin.left + innerW / 2}" y="${height - 10}" fill="#e9eef7" font-size="12" text-anchor="middle">${esc(xLabel)}</text>
          <text x="16" y="${margin.top + innerH / 2}" fill="#e9eef7" font-size="12" text-anchor="middle" transform="rotate(-90 16 ${margin.top + innerH / 2})">${esc(yLabel)}</text>
        </svg>
      </div>
      <div class="small" style="margin-top:8px;">
        Green = Pareto frontier • Yellow = selected model • Blue = other slices • Hover a point for exact model/TDP values
      </div>
    </div>
  `;
}

function renderTaskRankingSurface() {
  const root = document.getElementById("task-ranking-surface");
  if (!root) return;

  ensureSelectedModelAndTask();

  let rows = getVisibleTaskRows().filter(r => r.task_id === state.selectedTaskId);

  rows.sort((a, b) => {
    const fc = safeNum(b.fully_correct_rate) - safeNum(a.fully_correct_rate);
    if (fc !== 0) return fc;
    const pu = safeNum(b.pipeline_usable_rate) - safeNum(a.pipeline_usable_rate);
    if (pu !== 0) return pu;
    return safeNum(b.avg_score_percent) - safeNum(a.avg_score_percent);
  });

  if (!rows.length) {
    root.innerHTML = `<div class="loading">No rows available for selected task.</div>`;
    return;
  }

  const scoreScale = makeScale(rows.map(r => r.avg_score_percent), { higherIsBetter: true });
  const energyScale = makeScale(rows.map(r => r.avg_energy_j), { higherIsBetter: false });
  const tpsScale = makeScale(rows.map(r => r.avg_tokens_per_second), { higherIsBetter: true });
  const outTokScale = makeScale(rows.map(r => r.avg_output_tokens), { higherIsBetter: false });
  const score100Scale = makeScale(rows.map(r => r.avg_score_per_100_output_tokens), { higherIsBetter: true });
  const joutScale = makeScale(rows.map(r => r.avg_joules_per_output_token), { higherIsBetter: false });

  const taskPareto = state.pareto?.per_task_frontier?.[state.selectedTaskId]?.frontier || [];
  const frontierKeys = new Set(taskPareto.map(r => `${r.model}__${r.tdp_level}`));

  const chart = buildSvgScatterPlot({
    title: "Selected task frontier chart",
    subtitle: `${state.selectedTaskId} • each point is one model × TDP slice`,
    rows,
    xKey: "avg_energy_j",
    yKey: "fully_correct_rate",
    xLabel: "Average energy (J)",
    yLabel: "Fully correct rate",
    selectedPredicate: (r) => r.model === state.selectedModelName,
    frontierPredicate: (r) => frontierKeys.has(`${r.model}__${r.tdp_level}`),
  });

  root.innerHTML = `
    ${chart}
    <div class="scroll-x" style="margin-top:16px;">
      <table>
        <thead>
          <tr>
            <th>${thLabel("Rank", "model")}</th>
            <th>${thLabel("Model", "model")}</th>
            <th>${thLabel("Family", "model")}</th>
            <th>${thLabel("TDP", "tdp_level")}</th>
            <th>${thLabel("n", "benchmark_count")}</th>
            <th>${thLabel("Frontier", "pareto")}</th>
            <th>${thLabel("Fully Correct", "fully_correct_rate")}</th>
            <th>${thLabel("Pipeline", "pipeline_usable_rate")}</th>
            <th>${thLabel("Usable", "usable_output_rate")}</th>
            <th>${thLabel("Hard Failure", "hard_failure_rate")}</th>
            <th>${thLabel("Avg Score", "avg_score_percent")}</th>
            <th>${thLabel("Avg Energy", "avg_energy_j")}</th>
            <th>${thLabel("Tokens/s", "avg_tokens_per_second")}</th>
            <th>${thLabel("Out Tokens", "avg_output_tokens")}</th>
            <th>${thLabel("OutTok vs Best", "outtok_vs_best")}</th>
            <th>${thLabel("Score/100tok", "avg_score_per_100_output_tokens")}</th>
            <th>${thLabel("J/OutTok", "avg_joules_per_output_token")}</th>
            <th>${thLabel("Score/Wh vs Best", "scorewh_vs_best")}</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((r, idx) => {
            const onFrontier = frontierKeys.has(`${r.model}__${r.tdp_level}`);
            return `
              <tr class="task-row ${r.model === state.selectedModelName ? "selected" : ""}" data-model="${esc(r.model)}" data-task="${esc(r.task_id)}">
                <td>${idx + 1}</td>
                <td>${esc(r.model)}</td>
                <td>${esc(r.task_family)}</td>
                <td>${esc(r.tdp_level)}</td>
                <td>${r.benchmark_count ?? "—"}</td>
                <td>${onFrontier ? "yes" : ""}</td>
                <td class="${cssClassForRate(r.fully_correct_rate)}">${percent(r.fully_correct_rate)}</td>
                <td class="${cssClassForRate(r.pipeline_usable_rate)}">${percent(r.pipeline_usable_rate)}</td>
                <td class="${cssClassForRate(r.usable_output_rate)}">${percent(r.usable_output_rate)}</td>
                <td class="${cssClassForInverseRate(r.hard_failure_rate)}">${percent(r.hard_failure_rate)}</td>
                <td class="${cssClassFromScale(r.avg_score_percent, scoreScale)}">${number2(r.avg_score_percent)}%</td>
                <td class="${cssClassFromScale(r.avg_energy_j, energyScale)}">${energy(r.avg_energy_j)}</td>
                <td class="${cssClassFromScale(r.avg_tokens_per_second, tpsScale)}">${number2(r.avg_tokens_per_second)}</td>
                <td class="${cssClassFromScale(r.avg_output_tokens, outTokScale)}">${number2(r.avg_output_tokens)}</td>
                <td class="${cssClassForRelativeLow(r.outtok_vs_best)}">${r.outtok_vs_best == null ? "—" : ratio2(r.outtok_vs_best)}</td>
                <td class="${cssClassFromScale(r.avg_score_per_100_output_tokens, score100Scale)}">${number2(r.avg_score_per_100_output_tokens)}</td>
                <td class="${cssClassFromScale(r.avg_joules_per_output_token, joutScale)}">${number2(r.avg_joules_per_output_token)}</td>
                <td class="${cssClassForRelativeHigh(r.scorewh_vs_best)}">${r.scorewh_vs_best == null ? "—" : ratio2(r.scorewh_vs_best)}</td>
              </tr>
            `;
          }).join("")}
        </tbody>
      </table>
    </div>
  `;

  root.querySelectorAll(".task-row").forEach(row => {
    row.onclick = () => {
      state.selectedModelName = row.dataset.model;
      state.selectedTaskId = row.dataset.task;
      renderAll();
    };
  });
}

function renderModelTaskSurface() {
  const root = document.getElementById("model-task-surface");
  if (!root) return;

  if (!state.selectedModelName) {
    root.innerHTML = `<div class="loading">Select a model first.</div>`;
    return;
  }

  let rows = state.modelTaskTdp.filter(r => r.model === state.selectedModelName);
  if (state.selectedFamily !== "all") {
    rows = rows.filter(r => r.task_family === state.selectedFamily);
  }

  const grouped = new Map();
  for (const row of rows) {
    if (!grouped.has(row.task_id)) grouped.set(row.task_id, []);
    grouped.get(row.task_id).push(row);
  }

  const summaryRows = Array.from(grouped.entries()).map(([taskId, taskRows]) => ({
    task_id: taskId,
    task_family: taskRows[0]?.task_family || "unknown",
    benchmark_count: sum(taskRows.map(r => r.benchmark_count)),
    fully_correct_rate: avg(taskRows.map(r => r.fully_correct_rate)),
    pipeline_usable_rate: avg(taskRows.map(r => r.pipeline_usable_rate)),
    usable_output_rate: avg(taskRows.map(r => r.usable_output_rate)),
    hard_failure_rate: avg(taskRows.map(r => r.hard_failure_rate)),
    avg_score_percent: avg(taskRows.map(r => r.avg_score_percent)),
    avg_energy_j: avg(taskRows.map(r => r.avg_energy_j)),
    avg_tokens_per_second: avg(taskRows.map(r => r.avg_tokens_per_second)),
  }));

  summaryRows.sort((a, b) => safeNum(b.fully_correct_rate) - safeNum(a.fully_correct_rate));

  root.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>${thLabel("Task", "model")}</th>
          <th>${thLabel("Family", "model")}</th>
          <th>${thLabel("n", "benchmark_count")}</th>
          <th>${thLabel("Fully Correct", "fully_correct_rate")}</th>
          <th>${thLabel("Pipeline", "pipeline_usable_rate")}</th>
          <th>${thLabel("Usable", "usable_output_rate")}</th>
          <th>${thLabel("Hard Failure", "hard_failure_rate")}</th>
          <th>${thLabel("Avg Score", "avg_score_percent")}</th>
          <th>${thLabel("Avg Energy", "avg_energy_j")}</th>
          <th>${thLabel("Tokens/s", "avg_tokens_per_second")}</th>
        </tr>
      </thead>
      <tbody>
        ${summaryRows.map(r => `
          <tr class="pair-row ${r.task_id === state.selectedTaskId ? "selected" : ""}" data-task="${esc(r.task_id)}">
            <td>${esc(r.task_id)}</td>
            <td>${esc(r.task_family)}</td>
            <td>${r.benchmark_count}</td>
            <td class="${cssClassForRate(r.fully_correct_rate)}">${percent(r.fully_correct_rate)}</td>
            <td class="${cssClassForRate(r.pipeline_usable_rate)}">${percent(r.pipeline_usable_rate)}</td>
            <td class="${cssClassForRate(r.usable_output_rate)}">${percent(r.usable_output_rate)}</td>
            <td class="${cssClassForInverseRate(r.hard_failure_rate)}">${percent(r.hard_failure_rate)}</td>
            <td>${number2(r.avg_score_percent)}%</td>
            <td>${energy(r.avg_energy_j)}</td>
            <td>${number2(r.avg_tokens_per_second)}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;

  root.querySelectorAll(".pair-row").forEach(row => {
    row.onclick = () => {
      state.selectedTaskId = row.dataset.task;
      renderAll();
    };
  });
}

function renderTdpSurface() {
  const root = document.getElementById("tdp-surface");
  if (!root) return;

  if (!state.selectedModelName) {
    root.innerHTML = `<div class="loading">Select a model first.</div>`;
    return;
  }

  let rows = state.modelTaskTdp.filter(r => r.model === state.selectedModelName);
  if (state.selectedFamily !== "all") {
    rows = rows.filter(r => r.task_family === state.selectedFamily);
  }

  const grouped = new Map();
  for (const row of rows) {
    const key = String(row.tdp_level);
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key).push(row);
  }

  const tdpRows = Array.from(grouped.entries()).map(([tdp, sliceRows]) => ({
    tdp_level: tdp,
    benchmark_count: sum(sliceRows.map(r => r.benchmark_count)),
    fully_correct_rate: avg(sliceRows.map(r => r.fully_correct_rate)),
    pipeline_usable_rate: avg(sliceRows.map(r => r.pipeline_usable_rate)),
    usable_output_rate: avg(sliceRows.map(r => r.usable_output_rate)),
    hard_failure_rate: avg(sliceRows.map(r => r.hard_failure_rate)),
    avg_score_percent: avg(sliceRows.map(r => r.avg_score_percent)),
    avg_energy_j: avg(sliceRows.map(r => r.avg_energy_j)),
    avg_tokens_per_second: avg(sliceRows.map(r => r.avg_tokens_per_second)),
  })).sort((a, b) => safeNum(a.tdp_level) - safeNum(b.tdp_level));

  root.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>${thLabel("TDP", "tdp_level")}</th>
          <th>${thLabel("n", "benchmark_count")}</th>
          <th>${thLabel("Fully Correct", "fully_correct_rate")}</th>
          <th>${thLabel("Pipeline", "pipeline_usable_rate")}</th>
          <th>${thLabel("Usable", "usable_output_rate")}</th>
          <th>${thLabel("Hard Failure", "hard_failure_rate")}</th>
          <th>${thLabel("Avg Score", "avg_score_percent")}</th>
          <th>${thLabel("Avg Energy", "avg_energy_j")}</th>
          <th>${thLabel("Tokens/s", "avg_tokens_per_second")}</th>
        </tr>
      </thead>
      <tbody>
        ${tdpRows.map(r => `
          <tr>
            <td>${esc(r.tdp_level)}</td>
            <td>${r.benchmark_count}</td>
            <td class="${cssClassForRate(r.fully_correct_rate)}">${percent(r.fully_correct_rate)}</td>
            <td class="${cssClassForRate(r.pipeline_usable_rate)}">${percent(r.pipeline_usable_rate)}</td>
            <td class="${cssClassForRate(r.usable_output_rate)}">${percent(r.usable_output_rate)}</td>
            <td class="${cssClassForInverseRate(r.hard_failure_rate)}">${percent(r.hard_failure_rate)}</td>
            <td>${number2(r.avg_score_percent)}%</td>
            <td>${energy(r.avg_energy_j)}</td>
            <td>${number2(r.avg_tokens_per_second)}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

function renderTaskDetail() {
  const root = document.getElementById("task-detail-surface");
  if (!root) return;

  if (!state.selectedModelName || !state.selectedTaskId) {
    root.innerHTML = `<div class="loading">Select a model and a task.</div>`;
    return;
  }

  const rows = state.modelTaskTdp
    .filter(r => r.model === state.selectedModelName && r.task_id === state.selectedTaskId)
    .sort((a, b) => safeNum(a.tdp_level) - safeNum(b.tdp_level));

  if (!rows.length) {
    root.innerHTML = `<div class="loading">No task detail available for selected model × task.</div>`;
    return;
  }

  root.innerHTML = `
    <div class="card">
      <h3>${esc(state.selectedModelName)} × ${esc(state.selectedTaskId)}</h3>
      <div class="scroll-x">
        <table>
          <thead>
            <tr>
              <th>${thLabel("TDP", "tdp_level")}</th>
              <th>${thLabel("n", "benchmark_count")}</th>
              <th>${thLabel("Fully Correct", "fully_correct_rate")}</th>
              <th>${thLabel("Pipeline", "pipeline_usable_rate")}</th>
              <th>${thLabel("Usable", "usable_output_rate")}</th>
              <th>${thLabel("Hard Failure", "hard_failure_rate")}</th>
              <th>${thLabel("Avg Score", "avg_score_percent")}</th>
              <th>${thLabel("Avg Energy", "avg_energy_j")}</th>
              <th>${thLabel("Avg tok/s", "avg_tokens_per_second")}</th>
              <th>${thLabel("GPU", "gpu_name")}</th>
              <th>${thLabel("Runtime", "runtime_residency_status")}</th>
            </tr>
          </thead>
          <tbody>
            ${rows.map(r => `
              <tr>
                <td>${esc(r.tdp_level)}</td>
                <td>${r.benchmark_count ?? "—"}</td>
                <td class="${cssClassForRate(r.fully_correct_rate)}">${percent(r.fully_correct_rate)}</td>
                <td class="${cssClassForRate(r.pipeline_usable_rate)}">${percent(r.pipeline_usable_rate)}</td>
                <td class="${cssClassForRate(r.usable_output_rate)}">${percent(r.usable_output_rate)}</td>
                <td class="${cssClassForInverseRate(r.hard_failure_rate)}">${percent(r.hard_failure_rate)}</td>
                <td>${number2(r.avg_score_percent)}%</td>
                <td>${energy(r.avg_energy_j)}</td>
                <td>${number2(r.avg_tokens_per_second)}</td>
                <td>${esc(r.gpu_name || "—")}</td>
                <td>${esc(r.runtime_residency_status || r.canonical_runtime || "—")}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function normalizeFailureDistribution(items) {
  if (!Array.isArray(items)) return [];
  return items
    .map(item => ({
      name: String(item?.name ?? "unknown"),
      count: safeNum(item?.count),
      rate: safeNum(item?.rate),
    }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
}

function computeRunsWithFailureSignals(row) {
  const benchmarkCount = safeNum(row?.benchmark_count);
  const stageDistribution = normalizeFailureDistribution(row?.failure_stage_distribution);
  const nonSuccessStageCount = sum(
    stageDistribution
      .filter(item => item.name !== "success" && item.name !== "unknown")
      .map(item => item.count)
  );

  const cappedRunsWithSignals = Math.min(benchmarkCount, nonSuccessStageCount);
  const runsWithSignalsRate = benchmarkCount > 0 ? cappedRunsWithSignals / benchmarkCount : 0;

  return {
    runsWithSignals: cappedRunsWithSignals,
    runsWithSignalsRate,
  };
}

function renderFailureSurface() {
  const root = document.getElementById("failure-surface");
  if (!root) return;

  const row = state.failureSurfaces.find(r => r.model === state.selectedModelName && r.task_id === state.selectedTaskId);
  if (!row) {
    root.innerHTML = `<div class="loading">No failure surface available for selected model × task.</div>`;
    return;
  }

  const benchmarkCount = safeNum(row.benchmark_count);
  const failureRecordCount = safeNum(row.failure_record_count);
  const failureSignalDensity = benchmarkCount > 0 ? failureRecordCount / benchmarkCount : 0;
  const { runsWithSignals, runsWithSignalsRate } = computeRunsWithFailureSignals(row);

  const makeChips = (items) =>
    normalizeFailureDistribution(items).map(item =>
      `<span class="failure-chip">${esc(item.name)} • ${item.count} • ${percent(item.rate)}</span>`
    ).join("");

  const renderDistributionTable = (title, key, items) => `
    <div class="card">
      <h3>${esc(title)}</h3>
      <div class="scroll-x">
        <table>
          <thead>
            <tr>
              <th>${thLabel("Name", key)}</th>
              <th>${thLabel("Count", key)}</th>
              <th>${thLabel("Rate", key)}</th>
            </tr>
          </thead>
          <tbody>
            ${normalizeFailureDistribution(items).map(item => `
              <tr>
                <td>${esc(item.name)}</td>
                <td>${item.count}</td>
                <td>${percent(item.rate)}</td>
              </tr>
            `).join("") || `
              <tr><td colspan="3">No data.</td></tr>
            `}
          </tbody>
        </table>
      </div>
    </div>
  `;

  root.innerHTML = `
    <div class="grid grid-2">
      <div class="card">
        <h3>Failure summary</h3>
        <div class="stats">
          ${buildStat("Benchmarks", benchmarkCount || "—", "benchmark_count")}
          ${buildStat("Failure records", failureRecordCount || "—", "failure_record_count")}
          ${buildStat("Signals / run", number2(failureSignalDensity), "failure_signal_density")}
          ${buildStat("Runs with failure signals", runsWithSignals || "0", "runs_with_failure_signals")}
          ${buildStat("Runs with failure signals %", percent(runsWithSignalsRate), "runs_with_failure_signals_rate")}
          ${buildStat("Top stage", esc(row.dominant_failure_stage?.[0]?.name || "—"), "failure_record_count")}
          ${buildStat("Top type", esc(row.dominant_failure_type?.[0]?.name || "—"), "failure_record_count")}
          ${buildStat("Top subtype", esc(row.dominant_failure_subtype?.[0]?.name || "—"), "failure_record_count")}
        </div>

        <h3>Dominant stages</h3>
        <div>${makeChips(row.dominant_failure_stage) || '<span class="small">No stage data.</span>'}</div>

        <h3 style="margin-top:16px;">Dominant types</h3>
        <div>${makeChips(row.dominant_failure_type) || '<span class="small">No type data.</span>'}</div>

        <h3 style="margin-top:16px;">Dominant subtypes</h3>
        <div>${makeChips(row.dominant_failure_subtype) || '<span class="small">No subtype data.</span>'}</div>
      </div>

      <div class="grid" style="gap:16px;">
        ${renderDistributionTable("Subtype distribution", "failure_record_count", row.failure_subtype_distribution)}
        ${renderDistributionTable("Type distribution", "failure_record_count", row.failure_type_distribution)}
        ${renderDistributionTable("Stage distribution", "failure_record_count", row.failure_stage_distribution)}
      </div>
    </div>
  `;
}

function renderParetoFrontier() {
  const root = document.getElementById("pareto-frontier-surface");
  if (!root) return;
  if (!state.pareto) {
    root.innerHTML = `<div class="loading">No Pareto data loaded.</div>`;
    return;
  }

  const globalFrontier = state.pareto.global_model_frontier?.frontier || [];
  const globalDominated = state.pareto.global_model_frontier?.dominated || [];
  const allGlobalRows = [...globalFrontier, ...globalDominated];

  const perTask = state.pareto.per_task_frontier || {};
  const selectedTask = state.selectedTaskId && perTask[state.selectedTaskId] ? perTask[state.selectedTaskId] : null;
  const selectedTaskRows = selectedTask ? [...(selectedTask.frontier || []), ...(selectedTask.dominated || [])] : [];
  const selectedTaskFrontierKeys = new Set((selectedTask?.frontier || []).map(r => `${r.model}__${r.tdp_level}`));
  const globalFrontierKeys = new Set(globalFrontier.map(r => r.model));

  const globalChart = buildSvgScatterPlot({
    title: "Global model frontier chart",
    subtitle: "Each point is a model. Lower energy and higher fully-correct are better.",
    rows: allGlobalRows,
    xKey: "avg_energy_j",
    yKey: "fully_correct_rate",
    xLabel: "Average energy (J)",
    yLabel: "Fully correct rate",
    selectedPredicate: (r) => r.model === state.selectedModelName,
    frontierPredicate: (r) => globalFrontierKeys.has(r.model),
  });

  const taskChart = selectedTask
    ? buildSvgScatterPlot({
        title: `Task frontier chart: ${state.selectedTaskId}`,
        subtitle: "Each point is a model × TDP slice for the selected task.",
        rows: selectedTaskRows,
        xKey: "avg_energy_j",
        yKey: "fully_correct_rate",
        xLabel: "Average energy (J)",
        yLabel: "Fully correct rate",
        selectedPredicate: (r) => r.model === state.selectedModelName,
        frontierPredicate: (r) => selectedTaskFrontierKeys.has(`${r.model}__${r.tdp_level}`),
      })
    : `<div class="loading">No selected-task frontier available.</div>`;

  root.innerHTML = `
    <div class="grid grid-2">
      ${globalChart}
      ${taskChart}
    </div>
  `;
}

async function renderSystemSummary() {
  const root = document.getElementById("system-summary");
  if (!root) return;

  const tasks = uniqueSorted(state.modelTaskTdp.map(r => r.task_id));
  const families = uniqueSorted(state.modelTaskTdp.map(r => r.task_family));
  const tdps = uniqueSorted(state.modelTaskTdp.map(r => r.tdp_level));
  const gpus = uniqueSorted(state.modelTaskTdp.map(r => r.gpu_name || "unknown"));

  root.innerHTML = `
    <div class="card"><h3>Models</h3><div class="stat-value">${state.modelRankings.length}</div></div>
    <div class="card"><h3>Tasks</h3><div class="stat-value">${tasks.length}</div></div>
    <div class="card"><h3>Families</h3><div class="stat-value">${families.length}</div></div>
    <div class="card"><h3>TDP Levels</h3><div class="stat-value">${tdps.length}</div></div>
    <div class="card"><h3>GPUs</h3><div class="stat-value">${gpus.length}</div></div>
    <div class="card"><h3>Task Registry Rows</h3><div class="stat-value">${state.taskRegistry.length}</div></div>
  `;
}

function normalizeInventorySections(dataIndex) {
  const duckdb = [
    { path: "duckdb_model_rankings.json", label: "duckdb_model_rankings.json", meta: "DuckDB export" },
    { path: "duckdb_task_rankings.json", label: "duckdb_task_rankings.json", meta: "DuckDB export" },
    { path: "duckdb_model_task_tdp.json", label: "duckdb_model_task_tdp.json", meta: "DuckDB export" },
    { path: "duckdb_pareto_frontiers.json", label: "duckdb_pareto_frontiers.json", meta: "DuckDB export" },
    { path: "duckdb_task_registry.json", label: "duckdb_task_registry.json", meta: "Task registry export" },
    { path: "duckdb_failure_surfaces.json", label: "duckdb_failure_surfaces.json", meta: "Failure surface export" },
  ];

  if (!dataIndex || !dataIndex.sections) {
    return { duckdb, other: [] };
  }

  const flattenSection = (paths, meta) => (paths || []).map(path => ({ path, label: path, meta }));

  const other = [
    ...flattenSection(dataIndex.sections.registries, "registry"),
    ...flattenSection(dataIndex.sections.verification, "verification"),
    ...flattenSection(dataIndex.sections.joined, "joined output"),
    ...flattenSection(dataIndex.sections.failures, "failure output"),
    ...Object.entries(dataIndex.sections.analysis || {}).flatMap(([family, paths]) =>
      (paths || []).map(path => ({ path, label: path, meta: `analysis • ${family}` }))
    ),
  ];

  return { duckdb, other };
}

function renderBrowserTabs() {
  const root = document.getElementById("browser-tabs");
  if (!root) return;

  const tabs = [
    { key: "duckdb", label: "DuckDB Exports" },
    { key: "other", label: "Other JSON" },
  ];

  root.innerHTML = "";
  tabs.forEach(tab => {
    const btn = document.createElement("button");
    btn.className = `tab-btn ${state.browserTab === tab.key ? "active" : ""}`;
    btn.textContent = tab.label;
    btn.onclick = () => {
      state.browserTab = tab.key;
      state.selectedPath = null;
      renderBrowserTabs();
      renderBrowserList();
      renderPreviewMessage("Select a file to preview.");
    };
    root.appendChild(btn);
  });
}

function getBrowserEntries() {
  const sections = normalizeInventorySections(state.dataIndex);
  return state.browserTab === "duckdb" ? sections.duckdb : sections.other;
}

function renderBrowserList() {
  const root = document.getElementById("browser-list");
  if (!root) return;

  const entries = getBrowserEntries();
  root.innerHTML = "";

  entries.forEach(entry => {
    const btn = document.createElement("button");
    btn.className = `browser-item ${state.selectedPath === entry.path ? "active" : ""}`;
    btn.innerHTML = `
      <div class="browser-item-title">${esc(entry.label)}</div>
      <div class="browser-item-meta">${esc(entry.meta)}</div>
    `;
    btn.onclick = async () => {
      state.selectedPath = entry.path;
      renderBrowserList();
      await renderJsonPreview(entry.path);
    };
    root.appendChild(btn);
  });

  if (entries.length === 0) {
    root.innerHTML = `<div class="loading">No files available in this section.</div>`;
  }
}

function renderPreviewMessage(message) {
  const preview = document.getElementById("json-preview");
  if (preview) preview.textContent = message;
}

async function renderJsonPreview(path) {
  try {
    renderPreviewMessage(`Loading ${path} ...`);
    const data = await loadJson(`./data/${path}`);
    renderPreviewMessage(JSON.stringify(data, null, 2));
  } catch (error) {
    renderPreviewMessage(`Failed to load preview for ${path}: ${error.message}`);
  }
}

function bindChartTooltips() {
  const tooltip = document.getElementById("chart-tooltip");
  if (!tooltip) return;

  const points = document.querySelectorAll(".chart-point");
  const hideTooltip = () => { tooltip.style.display = "none"; };

  points.forEach(point => {
    point.addEventListener("mouseenter", () => {
      const title = point.dataset.ttTitle || "";
      const body = (point.dataset.ttBody || "")
        .split("||")
        .filter(Boolean)
        .map(line => `<div class="tt-line">${esc(line)}</div>`)
        .join("");
      tooltip.innerHTML = `<div class="tt-title">${esc(title)}</div>${body}`;
      tooltip.style.display = "block";
    });

    point.addEventListener("mousemove", (event) => {
      tooltip.style.left = `${event.clientX + 16}px`;
      tooltip.style.top = `${event.clientY + 16}px`;
    });

    point.addEventListener("mouseleave", hideTooltip);
  });
}

function bindHelpTooltips() {
  const tooltip = document.getElementById("help-tooltip");
  if (!tooltip) return;

  const anchors = document.querySelectorAll(".help-anchor");
  const hideTooltip = () => { tooltip.style.display = "none"; };

  anchors.forEach(anchor => {
    anchor.addEventListener("mouseenter", () => {
      const title = anchor.dataset.helpTitle || "";
      const body = anchor.dataset.helpBody || "";
      tooltip.innerHTML = `<div class="tt-title">${esc(title)}</div><div class="tt-line">${esc(body)}</div>`;
      tooltip.style.display = "block";
    });

    anchor.addEventListener("mousemove", (event) => {
      tooltip.style.left = `${event.clientX + 16}px`;
      tooltip.style.top = `${event.clientY + 16}px`;
    });

    anchor.addEventListener("mouseleave", hideTooltip);
  });
}

function bindControls() {
  const modelSelector = document.getElementById("model-selector");
  const taskSelector = document.getElementById("task-selector");
  const familySelector = document.getElementById("family-selector");
  const modelSearch = document.getElementById("model-search");
  const taskSearch = document.getElementById("task-search");
  const focusBtn = document.getElementById("focus-pair-btn");
  const clearBtn = document.getElementById("clear-focus-btn");

  if (modelSelector) modelSelector.onchange = (e) => { state.selectedModelName = e.target.value; renderAll(); };
  if (taskSelector) taskSelector.onchange = (e) => { state.selectedTaskId = e.target.value; renderAll(); };
  if (familySelector) familySelector.onchange = (e) => { state.selectedFamily = e.target.value; ensureSelectedModelAndTask(); renderAll(); };
  if (modelSearch) modelSearch.oninput = (e) => { state.modelSearch = e.target.value; ensureSelectedModelAndTask(); renderAll(); };
  if (taskSearch) taskSearch.oninput = (e) => { state.taskSearch = e.target.value; renderAll(); };
  if (focusBtn) focusBtn.onclick = () => { state.focusSelectedPairOnly = true; renderAll(); };
  if (clearBtn) clearBtn.onclick = () => { state.focusSelectedPairOnly = false; renderAll(); };
}

function renderAll() {
  buildSelectors();
  renderModelTable();
  renderSelectedModelDetail();
  renderTaskRegistry();
  renderTaskRankingSurface();
  renderModelTaskSurface();
  renderTdpSurface();
  renderTaskDetail();
  renderFailureSurface();
  renderParetoFrontier();
  renderSystemSummary();
  renderBrowserTabs();
  renderBrowserList();
  bindChartTooltips();
  bindHelpTooltips();
}

async function main() {
  try {
    const [modelRankings, taskRankings, modelTaskTdp, taskRegistry, failureSurfaces, pareto, dataIndex] = await Promise.all([
      loadModelRankings(),
      loadTaskRankings(),
      loadModelTaskTdp(),
      loadTaskRegistry(),
      loadFailureSurfaces(),
      loadPareto(),
      loadDataIndex(),
    ]);

    state.modelRankings = modelRankings.rows || [];
    state.taskRankings = taskRankings.rows || [];
    state.modelTaskTdp = modelTaskTdp.rows || [];
    state.taskRegistry = taskRegistry.rows || [];
    state.failureSurfaces = failureSurfaces.rows || [];
    state.pareto = pareto;
    state.dataIndex = dataIndex;

    ensureSelectedModelAndTask();
    bindControls();
    renderOverview(
      modelRankings.generated_at_utc ||
      taskRankings.generated_at_utc ||
      modelTaskTdp.generated_at_utc ||
      taskRegistry.generated_at_utc ||
      failureSurfaces.generated_at_utc ||
      pareto.generated_at_utc ||
      "unknown"
    );
    renderAll();
    renderPreviewMessage("Select a file to preview.");
  } catch (error) {
    console.error(error);
    const modelTable = document.getElementById("model-table");
    if (modelTable) {
      modelTable.innerHTML = `<div class="error">Failed to initialize UI: ${esc(error.message)}</div>`;
    }
    renderPreviewMessage(`Initialization failed: ${error.message}`);
  }
}

main();
