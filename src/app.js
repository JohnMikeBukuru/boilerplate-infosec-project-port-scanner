const $ = (sel) => document.querySelector(sel);

const listEl = $("#list");
const pillOverall = $("#pillOverall");
const passedCountEl = $("#passedCount");
const failedCountEl = $("#failedCount");
const totalCountEl = $("#totalCount");
const progressBar = $("#progressBar");
const timestampEl = $("#timestamp");
const stdoutEl = $("#stdout");

const btnRefresh = $("#btnRefresh");
const autoRefresh = $("#autoRefresh");
const intervalSel = $("#interval");

const searchEl = $("#search");
const tabButtons = [...document.querySelectorAll(".tab")];

let state = {
  filter: "all",
  search: "",
  timer: null,
  lastPayload: null,
};

function formatTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

function renderSkeleton(count = 6) {
  listEl.innerHTML = "";
  for (let i = 0; i < count; i++) {
    const sk = document.createElement("div");
    sk.className = "skel";
    sk.innerHTML = `
      <div class="skel-row"></div>
      <div class="skel-row small"></div>
    `;
    listEl.appendChild(sk);
  }
}

function badgeForStatus(status) {
  if (status === "passed") return `<span class="badge ok">PASSED</span>`;
  if (status === "failed") return `<span class="badge bad">FAILED</span>`;
  if (status === "running") return `<span class="badge warn">RUNNING</span>`;
  return `<span class="badge warn">UNKNOWN</span>`;
}

function pillForChallenge(challenge, runState) {
  // runState takes precedence visually
  if (runState === "running") {
    return { cls: "pill warn", text: "⏳ Tests are running…" };
  }
  if (challenge === "passed") return { cls: "pill ok", text: "✅ Challenge passed" };
  if (challenge === "failed") return { cls: "pill bad", text: "❌ Challenge failed" };
  return { cls: "pill warn", text: "⏳ Waiting…" };
}

function normalizePayload(parsed) {
  const tests = Array.isArray(parsed?.tests) ? parsed.tests : [];

  // Ensure hint/status always exist for UI + FCC client style messages
  for (const t of tests) {
    if (!("hint" in t)) t.hint = "";
    if (!("status" in t)) t.status = "unknown";
    if (!("name" in t)) t.name = "";
  }

  return {
    ok: Boolean(parsed?.ok),
    state: parsed?.state || "", // ✅ NEW
    message: parsed?.message || "",
    challenge: parsed?.challenge || "",
    tests,
    stdout: parsed?.stdout || "",
    timestamp: parsed?.timestamp || "",
  };
}

function computeCounts(tests) {
  let passed = 0,
    failed = 0;
  for (const t of tests) {
    if (t.status === "passed") passed++;
    else if (t.status === "failed") failed++;
  }
  return { passed, failed, total: tests.length };
}

function applyFilters(tests) {
  const q = state.search.trim().toLowerCase();
  return tests.filter((t) => {
    const matchesTab = state.filter === "all" ? true : t.status === state.filter;
    const matchesSearch = !q
      ? true
      : String(t.name || "").toLowerCase().includes(q) ||
        String(t.hint || "").toLowerCase().includes(q);
    return matchesTab && matchesSearch;
  });
}

function renderList(tests) {
  if (!tests.length) {
    listEl.innerHTML = `
      <div class="item">
        <div class="item-top">
          <div class="name">No tests to display</div>
          <span class="badge warn">EMPTY</span>
        </div>
        <div class="hint">Run <code>python main.py</code> and refresh.</div>
      </div>
    `;
    return;
  }

  listEl.innerHTML = "";
  const filtered = applyFilters(tests);

  if (!filtered.length) {
    listEl.innerHTML = `
      <div class="item">
        <div class="item-top">
          <div class="name">No matches</div>
          <span class="badge warn">FILTER</span>
        </div>
        <div class="hint">Try clearing search or switching tabs.</div>
      </div>
    `;
    return;
  }

  for (const t of filtered) {
    const row = document.createElement("div");
    row.className = "item";
    row.innerHTML = `
      <div class="item-top">
        <div class="name">${escapeHtml(t.name || "")}</div>
        ${badgeForStatus(t.status)}
      </div>
      <div class="hint">${escapeHtml(t.hint || "")}</div>
    `;
    listEl.appendChild(row);
  }
}

function renderTop(parsed) {
  const { passed, failed, total } = computeCounts(parsed.tests);

  const pill = pillForChallenge(parsed.challenge, parsed.state);
  pillOverall.className = pill.cls;
  pillOverall.textContent = pill.text;

  passedCountEl.textContent = total ? String(passed) : "—";
  failedCountEl.textContent = total ? String(failed) : "—";
  totalCountEl.textContent = total ? String(total) : "—";

  const progress = total ? Math.round((passed / total) * 100) : 0;
  progressBar.style.width = `${progress}%`;

  timestampEl.textContent = parsed.timestamp ? `Last run: ${formatTime(parsed.timestamp)}` : "—";
}

function renderStdout(parsed) {
  stdoutEl.textContent = parsed.stdout || "";
}

function renderEmptyState(message) {
  pillOverall.className = "pill warn";
  pillOverall.textContent = "⏳ Waiting for first run";

  passedCountEl.textContent = "—";
  failedCountEl.textContent = "—";
  totalCountEl.textContent = "—";
  progressBar.style.width = "0%";
  timestampEl.textContent = "—";
  stdoutEl.textContent = "";

  listEl.innerHTML = `
    <div class="item">
      <div class="item-top">
        <div class="name">No results yet</div>
        <span class="badge warn">WAITING</span>
      </div>
      <div class="hint">${escapeHtml(
        message || "You must start typing your solution in port_scanner.py and run: python main.py"
      )}</div>
    </div>
  `;
}

function renderRunningState(parsed) {
  // Keep top pill as running, and show a nice message on the left.
  renderTop(parsed);

  listEl.innerHTML = `
    <div class="item">
      <div class="item-top">
        <div class="name">Tests are still running…</div>
        <span class="badge warn">RUNNING</span>
      </div>
      <div class="hint">
        Please wait until <code>python main.py</code> finishes, then refresh.
      </div>
    </div>
  `;

  // stdout might be empty at start; keep what we have
  renderStdout(parsed);
}

function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function fetchResult() {
  const res = await fetch("/result", { cache: "no-store" });
  const text = await res.text();
  let parsed;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new Error(text || "Invalid JSON response from /result");
  }
  return normalizePayload(parsed);
}

async function refresh() {
  renderSkeleton();

  try {
    const parsed = await fetchResult();
    state.lastPayload = parsed;

    // Not started yet
    if (parsed.ok === false) {
      renderEmptyState(parsed.message);
      return;
    }

    // New state feature: running
    if (parsed.state === "running") {
      renderRunningState(parsed);
      return;
    }

    // Done / normal
    renderTop(parsed);
    renderList(parsed.tests);
    renderStdout(parsed);
  } catch (e) {
    listEl.innerHTML = `
      <div class="item">
        <div class="item-top">
          <div class="name">Failed to load /result</div>
          <span class="badge bad">ERROR</span>
        </div>
        <div class="hint">${escapeHtml(e?.message || String(e))}</div>
      </div>
    `;
  }
}

function setFilter(next) {
  state.filter = next;

  for (const b of tabButtons) {
    b.classList.toggle("active", b.dataset.filter === next);
  }

  if (state.lastPayload) renderList(state.lastPayload.tests);
}

function setSearch(q) {
  state.search = q;
  if (state.lastPayload) renderList(state.lastPayload.tests);
}

function stopPolling() {
  if (state.timer) clearInterval(state.timer);
  state.timer = null;
}

function startPolling() {
  stopPolling();
  if (!autoRefresh.checked) return;

  const ms = Number(intervalSel.value || "3000");
  state.timer = setInterval(() => {
    refreshQuiet();
  }, ms);
}

async function refreshQuiet() {
  try {
    const parsed = await fetchResult();
    state.lastPayload = parsed;

    if (parsed.ok === false) {
      renderEmptyState(parsed.message);
      return;
    }

    if (parsed.state === "running") {
      renderRunningState(parsed);
      return;
    }

    renderTop(parsed);
    renderList(parsed.tests);
    renderStdout(parsed);
  } catch {
    // ignore transient errors during polling
  }
}

// UI events
btnRefresh.addEventListener("click", () => refresh());

autoRefresh.addEventListener("change", () => startPolling());
intervalSel.addEventListener("change", () => startPolling());

searchEl.addEventListener("input", (e) => setSearch(e.target.value));

for (const b of tabButtons) {
  b.addEventListener("click", () => setFilter(b.dataset.filter));
}

// Initial load
renderSkeleton();
refresh().then(() => startPolling());
