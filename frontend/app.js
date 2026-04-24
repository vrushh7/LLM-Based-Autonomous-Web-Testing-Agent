/* ============================================================
   LLM Driven Autonomous Web Testing Agent — Frontend Logic
   ============================================================ */

const API_BASE = 'http://localhost:8000';

/* ---------- State ---------- */
const state = {
  sessions: [],          // { id, name, status: 'running'|'pass'|'fail', payload, instruction }
  activeSessionId: null,
  isRunning: false,
  view: 'tests',
  history: [],
  expandedHistory: new Set(),
};

let sessionCounter = 0;
const newSessionId = () => `s${Date.now()}_${++sessionCounter}`;

/* ---------- DOM refs ---------- */
const $ = (id) => document.getElementById(id);

const els = {
  healthDot: $('healthDot'),
  healthText: $('healthText'),
  themeToggle: $('themeToggle'),
  navTabs: document.querySelectorAll('.nav-tab'),
  views: { tests: $('view-tests'), history: $('view-history') },

  sessionTabs: $('sessionTabs'),
  newSessionBtn: $('newSessionBtn'),
  sessionCountHint: $('sessionCountHint'),

  welcomeScreen: $('welcomeScreen'),
  runningScreen: $('runningScreen'),
  resultScreen: $('resultScreen'),
  runningSub: $('runningSub'),

  verdictBanner: $('verdictBanner'),
  verdictIcon: $('verdictIcon'),
  verdictTitle: $('verdictTitle'),
  verdictMeta: $('verdictMeta'),
  resultInstruction: $('resultInstruction'),
  stepsList: $('stepsList'),
  stepsCount: $('stepsCount'),
  shotsGrid: $('shotsGrid'),
  shotsCount: $('shotsCount'),
  deleteSessionBtn: $('deleteSessionBtn'),

  instructionInput: $('instructionInput'),
  urlInput: $('urlInput'),
  forceFreshToggle: $('forceFreshToggle'),
  micBtn: $('micBtn'),
  runBtn: $('runBtn'),
  exampleChips: document.querySelectorAll('.example-chip'),

  historyList: $('historyList'),
  refreshHistoryBtn: $('refreshHistoryBtn'),

  toastContainer: $('toastContainer'),
  lightbox: $('lightbox'),
  lightboxImg: $('lightboxImg'),
  lightboxClose: $('lightboxClose'),
};

/* ---------- Init ---------- */
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  attachListeners();
  pingHealth();
  setInterval(pingHealth, 15000);
  loadHistory();
  renderSessionTabs();
  showWelcome();
});

/* ---------- Theme ---------- */
function initTheme() {
  const saved = localStorage.getItem('theme') || 'dark';
  document.documentElement.setAttribute('data-theme', saved);
}
function toggleTheme() {
  const cur = document.documentElement.getAttribute('data-theme');
  const next = cur === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
}

/* ---------- Listeners ---------- */
function attachListeners() {
  els.themeToggle.addEventListener('click', toggleTheme);

  els.navTabs.forEach((btn) => {
    btn.addEventListener('click', () => switchView(btn.dataset.view));
  });

  els.newSessionBtn.addEventListener('click', () => {
    state.activeSessionId = null;
    showWelcome();
    renderSessionTabs();
    els.instructionInput.focus();
  });

  els.runBtn.addEventListener('click', runTest);
  els.instructionInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      runTest();
    }
  });

  els.exampleChips.forEach((chip) => {
    chip.addEventListener('click', () => {
      els.instructionInput.value = chip.dataset.prompt;
      els.instructionInput.focus();
    });
  });

  els.deleteSessionBtn.addEventListener('click', () => {
    if (state.activeSessionId) closeSession(state.activeSessionId);
  });

  els.refreshHistoryBtn.addEventListener('click', loadHistory);

  els.micBtn.addEventListener('click', toggleVoiceInput);

  els.lightboxClose.addEventListener('click', closeLightbox);
  els.lightbox.addEventListener('click', (e) => {
    if (e.target === els.lightbox) closeLightbox();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeLightbox();
  });
}

/* ---------- View switching ---------- */
function switchView(view) {
  state.view = view;
  els.navTabs.forEach((b) => b.classList.toggle('active', b.dataset.view === view));
  Object.entries(els.views).forEach(([k, el]) => el.classList.toggle('active', k === view));
  if (view === 'history') loadHistory();
}

/* ---------- Health ---------- */
async function pingHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`, { cache: 'no-store' });
    if (!res.ok) throw new Error('bad status');
    const data = await res.json();
    setHealth('online', 'ONLINE');
    return data;
  } catch {
    setHealth('offline', 'OFFLINE');
    return null;
  }
}
function setHealth(cls, text) {
  els.healthDot.classList.remove('online', 'offline');
  els.healthText.classList.remove('online', 'offline');
  els.healthDot.classList.add(cls);
  els.healthText.classList.add(cls);
  els.healthText.textContent = text;
}

/* ---------- Session model ---------- */
function createSession(instruction) {
  const id = newSessionId();
  const session = {
    id,
    name: shortName(instruction),
    instruction,
    status: 'running',
    payload: null,
  };
  state.sessions.unshift(session);
  state.activeSessionId = id;
  renderSessionTabs();
  return session;
}
function getSession(id) { return state.sessions.find((s) => s.id === id); }
function setActiveSession(id) {
  state.activeSessionId = id;
  renderSessionTabs();
  const s = getSession(id);
  if (!s) { showWelcome(); return; }
  if (s.status === 'running') showRunning(s.instruction);
  else if (s.payload) renderSessionResult(s);
}
function closeSession(id) {
  const idx = state.sessions.findIndex((s) => s.id === id);
  if (idx === -1) return;
  state.sessions.splice(idx, 1);
  if (state.activeSessionId === id) {
    const next = state.sessions[0];
    if (next) setActiveSession(next.id);
    else { state.activeSessionId = null; showWelcome(); }
  }
  renderSessionTabs();
}
function shortName(instruction) {
  const cleaned = instruction.replace(/[^\w\s]/g, '').trim();
  const words = cleaned.split(/\s+/).slice(0, 4).join(' ');
  return words.length > 32 ? words.slice(0, 32) + '…' : words || 'Test';
}

/* ---------- Session tabs render ---------- */
function renderSessionTabs() {
  els.sessionTabs.innerHTML = '';
  state.sessions.forEach((s) => {
    const tab = document.createElement('div');
    tab.className = 'session-tab' + (s.id === state.activeSessionId ? ' active' : '');
    tab.innerHTML = `
      <span class="tab-dot ${s.status}"></span>
      <span class="tab-name" title="${escapeAttr(s.instruction)}">${escapeHtml(s.name)}</span>
      <button class="tab-close" title="Close">×</button>
    `;
    tab.addEventListener('click', (e) => {
      if (e.target.classList.contains('tab-close')) {
        e.stopPropagation();
        closeSession(s.id);
      } else {
        setActiveSession(s.id);
      }
    });
    els.sessionTabs.appendChild(tab);
  });
  els.sessionCountHint.textContent =
    `${state.sessions.length} active session${state.sessions.length === 1 ? '' : 's'}`;
}

/* ---------- Screen toggles ---------- */
function showWelcome() {
  els.welcomeScreen.classList.remove('hidden');
  els.runningScreen.classList.add('hidden');
  els.resultScreen.classList.add('hidden');
}
function showRunning(instruction) {
  els.welcomeScreen.classList.add('hidden');
  els.runningScreen.classList.remove('hidden');
  els.resultScreen.classList.add('hidden');
  els.runningSub.textContent = truncate(instruction, 90);
}
function showResult() {
  els.welcomeScreen.classList.add('hidden');
  els.runningScreen.classList.add('hidden');
  els.resultScreen.classList.remove('hidden');
}

/* ---------- Run test ---------- */
async function runTest() {
  const instruction = els.instructionInput.value.trim();
  if (!instruction) {
    toast('Please enter a test instruction', 'warning');
    return;
  }
  if (state.isRunning) {
    toast('A test is already running', 'warning');
    return;
  }

  const url = els.urlInput.value.trim();
  const force_fresh = els.forceFreshToggle.checked;

  const session = createSession(instruction);
  state.isRunning = true;
  setRunBtnLoading(true);
  showRunning(instruction);

  try {
    const body = { instruction, force_fresh };
    if (url) body.url = url;

    const res = await fetch(`${API_BASE}/api/test`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.error || 'Test failed');

    const passed = !!data.report?.success;
    session.status = passed ? 'pass' : 'fail';
    session.payload = data;

    if (state.activeSessionId === session.id) {
      renderSessionResult(session);
    }
    renderSessionTabs();
    toast(
      passed
        ? `Test passed · ${data.report.summary?.passed_steps || 0}/${data.report.summary?.total_steps || 0} steps`
        : `Test failed · check details`,
      passed ? 'success' : 'error'
    );
    loadHistory();
    els.instructionInput.value = '';
  } catch (err) {
    session.status = 'fail';
    session.payload = { error: err.message };
    if (state.activeSessionId === session.id) renderSessionError(session, err.message);
    renderSessionTabs();
    toast(`Error: ${err.message}`, 'error');
  } finally {
    state.isRunning = false;
    setRunBtnLoading(false);
  }
}

function setRunBtnLoading(loading) {
  els.runBtn.disabled = loading;
  els.runBtn.querySelector('.run-icon').classList.toggle('hidden', loading);
  els.runBtn.querySelector('.run-spinner').classList.toggle('hidden', !loading);
  els.runBtn.querySelector('.run-label').textContent = loading ? 'Running…' : 'Run Test';
}

/* ---------- Render result ---------- */
function renderSessionResult(session) {
  const data = session.payload;
  const report = data.report;
  if (!report) { renderSessionError(session, 'No report returned'); return; }

  const passed = !!report.success;
  els.verdictBanner.className = `verdict-banner ${passed ? 'pass' : 'fail'}`;
  els.verdictIcon.textContent = passed ? '✓' : '✕';
  els.verdictTitle.textContent = passed ? 'PASS' : 'FAIL';

  const sum = report.summary || {};
  const exec = data.execution_summary || {};
  const dur = report.duration != null ? `${report.duration.toFixed(2)}s` : '—';
  const skipped = exec.skipped ?? 0;
  const skippedTxt = skipped > 0 ? ` · ${skipped} skipped` : '';
  els.verdictMeta.innerHTML =
    `${sum.passed_steps ?? 0}/${sum.total_steps ?? 0} steps · ${dur}${skippedTxt} · ` +
    `<a class="report-link" href="${API_BASE}/api/report/${encodeURIComponent(report.test_id || '')}/html" target="_blank" rel="noopener">${escapeHtml(report.test_id || '')} ↗</a>`;

  els.resultInstruction.textContent = report.instruction || session.instruction;

  // Validation issues banner (auto-repairs the schema applied)
  renderValidationIssues(data.validation_issues);

  const steps = report.execution?.steps ?? report.steps ?? [];
  renderSteps(steps);

  const screenshots = report.artifacts?.screenshots ?? [];
  renderShots(screenshots, steps);

  showResult();
}

function renderValidationIssues(issues) {
  // Inject (or remove) a callout above the result-grid
  const existing = document.getElementById('validationIssues');
  if (existing) existing.remove();
  if (!issues || !issues.length) return;
  const node = document.createElement('div');
  node.id = 'validationIssues';
  node.className = 'validation-issues';
  node.innerHTML = `
    <div class="vi-head">⚠️ Plan auto-repaired (${issues.length} issue${issues.length === 1 ? '' : 's'})</div>
    <ul class="vi-list">
      ${issues.map((m) => `<li>${escapeHtml(m)}</li>`).join('')}
    </ul>
  `;
  els.resultInstruction.insertAdjacentElement('afterend', node);
}

function renderSessionError(session, message) {
  els.verdictBanner.className = 'verdict-banner fail';
  els.verdictIcon.textContent = '✕';
  els.verdictTitle.textContent = 'ERROR';
  els.verdictMeta.textContent = 'Backend error';
  els.resultInstruction.textContent = session.instruction;
  els.stepsList.innerHTML = `<div class="empty-panel">${escapeHtml(message)}</div>`;
  els.stepsCount.textContent = '0';
  els.shotsGrid.innerHTML = `<div class="empty-panel">No screenshots</div>`;
  els.shotsCount.textContent = '0';
  showResult();
}

function renderSteps(steps) {
  els.stepsList.innerHTML = '';
  els.stepsCount.textContent = steps.length;
  if (!steps.length) {
    els.stepsList.innerHTML = `<div class="empty-panel">No steps recorded</div>`;
    return;
  }
  steps.forEach((step) => {
    const status = step.status || 'failed';
    const cls = status === 'success' ? 'pass' : status === 'skipped' ? 'skip' : 'fail';
    const label = status === 'success' ? 'PASS' : status === 'skipped' ? 'SKIP' : 'FAIL';
    const shotName = step.screenshot ? extractFilename(step.screenshot) : '';
    const item = document.createElement('div');
    item.className = `step-item ${cls}`;
    item.innerHTML = `
      <div class="step-num">${step.step ?? ''}</div>
      <div class="step-body">
        <div class="step-top">
          <span class="step-action">${escapeHtml(step.action || '')}</span>
        </div>
        <div class="step-desc">${escapeHtml(step.description || '')}</div>
        ${shotName ? `<div class="step-shot-name">📸 ${escapeHtml(shotName)}</div>` : ''}
        ${step.error ? `<div class="step-error">${escapeHtml(step.error)}</div>` : ''}
      </div>
      <div class="step-status ${cls}">${label}</div>
    `;
    els.stepsList.appendChild(item);
  });
}

function renderShots(shots, steps) {
  els.shotsGrid.innerHTML = '';
  // Backend doesn't currently return artifacts.screenshots; we always derive
  // from the per-step paths (which include the test_HHMMSS/ subfolder).
  let list = shots;
  if (!list || !list.length) {
    list = (steps || [])
      .filter((s) => s.screenshot)
      .map((s) => ({ path: s.screenshot, step: s.step }));
  }
  els.shotsCount.textContent = list.length;
  if (!list.length) {
    els.shotsGrid.innerHTML = `<div class="empty-panel">No screenshots captured</div>`;
    return;
  }
  list.forEach((shot) => {
    const raw = shot.path || shot.filename || '';
    const url = shotUrl(raw);
    if (!url) return;
    const label = extractFilename(raw);
    const card = document.createElement('div');
    card.className = 'shot-card';
    card.innerHTML = `
      <img src="${url}" alt="${escapeAttr(label)}" loading="lazy"
           onerror="this.parentElement.classList.add('shot-broken')" />
      <div class="shot-card-name" title="${escapeAttr(label)}">${escapeHtml(label)}</div>
    `;
    card.addEventListener('click', () => openLightbox(url));
    els.shotsGrid.appendChild(card);
  });
}

/* ---------- History ---------- */
async function loadHistory() {
  try {
    els.historyList.innerHTML = `<div class="empty-state">Loading…</div>`;
    const res = await fetch(`${API_BASE}/api/history?limit=30`);
    const data = await res.json();
    state.history = data.history || [];
    renderHistory();
  } catch {
    els.historyList.innerHTML = `<div class="empty-state">Could not load history. Is the backend running?</div>`;
  }
}

function renderHistory() {
  if (!state.history.length) {
    els.historyList.innerHTML = `<div class="empty-state">No tests yet. Run your first test from the Tests tab.</div>`;
    return;
  }
  els.historyList.innerHTML = '';
  state.history.forEach((item) => {
    const passed = item.status === 'PASS';
    const card = document.createElement('div');
    card.className = `history-card ${passed ? 'pass' : 'fail'}`;
    const ts = item.timestamp ? new Date(item.timestamp).toLocaleString() : '';
    const dur = item.duration != null ? `${Number(item.duration).toFixed(2)}s` : '—';

    card.innerHTML = `
      <div class="history-card-top">
        <div class="history-instr">${escapeHtml(item.instruction || '(no instruction)')}</div>
        <span class="history-badge ${passed ? 'pass' : 'fail'}">${passed ? '✓ PASS' : '✕ FAIL'}</span>
      </div>
      <div class="history-meta">
        <span>🕒 ${escapeHtml(ts)}</span>
        <span>⏱ ${escapeHtml(dur)}</span>
        <span>🆔 ${escapeHtml(item.test_id || '')}</span>
      </div>
      <div class="history-actions">
        <button class="history-action-btn" data-act="steps">📋 View steps</button>
        <button class="history-action-btn" data-act="shots">📸 Screenshots</button>
        <button class="history-action-btn danger" data-act="delete">🗑 Delete</button>
      </div>
      <div class="history-expand hidden" data-expand></div>
    `;

    const expand = card.querySelector('[data-expand]');
    card.querySelectorAll('.history-action-btn').forEach((btn) => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const act = btn.dataset.act;
        if (act === 'delete') return deleteReport(item.test_id);
        if (act === 'steps')  return toggleHistoryExpand(item.test_id, expand, 'steps');
        if (act === 'shots')  return toggleHistoryExpand(item.test_id, expand, 'shots');
      });
    });

    els.historyList.appendChild(card);
  });
}

async function toggleHistoryExpand(testId, container, mode) {
  if (container.dataset.mode === mode && !container.classList.contains('hidden')) {
    container.classList.add('hidden');
    container.dataset.mode = '';
    return;
  }
  container.classList.remove('hidden');
  container.dataset.mode = mode;
  container.innerHTML = `<div class="empty-panel">Loading…</div>`;
  try {
    const res = await fetch(`${API_BASE}/api/report/${encodeURIComponent(testId)}`);
    const data = await res.json();
    if (!data.success) throw new Error('not found');
    const report = data.report;
    if (mode === 'steps') {
      const steps = report.execution?.steps ?? [];
      container.innerHTML = '';
      const wrap = document.createElement('div');
      wrap.className = 'steps-list';
      if (!steps.length) wrap.innerHTML = `<div class="empty-panel">No steps</div>`;
      steps.forEach((step) => {
        const passed = step.status === 'success';
        const shotName = step.screenshot ? extractFilename(step.screenshot) : '';
        const item = document.createElement('div');
        item.className = `step-item ${passed ? 'pass' : 'fail'}`;
        item.innerHTML = `
          <div class="step-num">${step.step ?? ''}</div>
          <div class="step-body">
            <div class="step-top"><span class="step-action">${escapeHtml(step.action || '')}</span></div>
            <div class="step-desc">${escapeHtml(step.description || '')}</div>
            ${shotName ? `<div class="step-shot-name">📸 ${escapeHtml(shotName)}</div>` : ''}
            ${step.error ? `<div class="step-error">${escapeHtml(step.error)}</div>` : ''}
          </div>
          <div class="step-status ${passed ? 'pass' : 'fail'}">${passed ? 'PASS' : 'FAIL'}</div>
        `;
        wrap.appendChild(item);
      });
      container.appendChild(wrap);
    } else if (mode === 'shots') {
      const shots = report.artifacts?.screenshots ?? [];
      const list = shots.length
        ? shots
        : (report.execution?.steps ?? report.steps ?? [])
            .filter((s) => s.screenshot)
            .map((s) => ({ path: s.screenshot }));
      container.innerHTML = '';
      const grid = document.createElement('div');
      grid.className = 'shots-grid';
      if (!list.length) grid.innerHTML = `<div class="empty-panel">No screenshots</div>`;
      list.forEach((shot) => {
        const raw = shot.path || shot.filename || '';
        const url = shotUrl(raw);
        if (!url) return;
        const label = extractFilename(raw);
        const card = document.createElement('div');
        card.className = 'shot-card';
        card.innerHTML = `
          <img src="${url}" alt="${escapeAttr(label)}" loading="lazy"
               onerror="this.parentElement.classList.add('shot-broken')" />
          <div class="shot-card-name" title="${escapeAttr(label)}">${escapeHtml(label)}</div>
        `;
        card.addEventListener('click', () => openLightbox(url));
        grid.appendChild(card);
      });
      container.appendChild(grid);
    }
  } catch (err) {
    container.innerHTML = `<div class="empty-panel">Failed to load: ${escapeHtml(err.message)}</div>`;
  }
}

async function deleteReport(testId) {
  if (!confirm(`Delete test ${testId}?`)) return;
  try {
    const res = await fetch(`${API_BASE}/api/report/${encodeURIComponent(testId)}`, {
      method: 'DELETE',
    });
    if (!res.ok && res.status !== 404 && res.status !== 405) {
      throw new Error(`HTTP ${res.status}`);
    }
    toast('Report deleted', 'success');
    state.history = state.history.filter((h) => h.test_id !== testId);
    renderHistory();
  } catch (err) {
    // Backend may not implement DELETE — remove from UI anyway
    toast(`Removed from view (backend: ${err.message})`, 'warning');
    state.history = state.history.filter((h) => h.test_id !== testId);
    renderHistory();
  }
}

/* ---------- Voice input (Web Speech API) ---------- */
let recognition = null;
let isRecording = false;

function toggleVoiceInput() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    toast('Voice input not supported in this browser', 'warning');
    return;
  }
  if (isRecording) { stopVoice(); return; }

  recognition = new SR();
  recognition.lang = 'en-US';
  recognition.interimResults = true;
  recognition.continuous = false;

  const baseValue = els.instructionInput.value;
  recognition.onresult = (e) => {
    let transcript = '';
    for (let i = e.resultIndex; i < e.results.length; i++) {
      transcript += e.results[i][0].transcript;
    }
    els.instructionInput.value = (baseValue ? baseValue + ' ' : '') + transcript;
  };
  recognition.onerror = (e) => {
    toast(`Voice error: ${e.error}`, 'error');
    stopVoice();
  };
  recognition.onend = () => stopVoice();

  try {
    recognition.start();
    isRecording = true;
    els.micBtn.classList.add('recording');
    toast('Listening…', 'info');
  } catch (err) {
    toast(`Could not start voice input`, 'error');
  }
}
function stopVoice() {
  if (recognition) { try { recognition.stop(); } catch {} }
  isRecording = false;
  els.micBtn.classList.remove('recording');
}

/* ---------- Lightbox ---------- */
function openLightbox(url) {
  els.lightboxImg.src = url;
  els.lightbox.classList.remove('hidden');
}
function closeLightbox() {
  els.lightbox.classList.add('hidden');
  els.lightboxImg.src = '';
}

/* ---------- Toasts ---------- */
function toast(message, type = 'info') {
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = message;
  t.addEventListener('click', () => t.remove());
  els.toastContainer.appendChild(t);
  setTimeout(() => {
    t.style.opacity = '0';
    t.style.transition = 'opacity 0.3s';
    setTimeout(() => t.remove(), 300);
  }, type === 'error' ? 6000 : 3500);
}

/* ---------- Helpers ---------- */
function extractFilename(p) {
  return String(p || '').replace(/\\/g, '/').split('/').pop();
}
/**
 * Build a URL the backend can serve from /api/screenshot/{path:path}.
 * Backend roots paths at config.SCREENSHOTS_DIR (./screenshots), so we strip
 * everything up to and including 'screenshots/' from the absolute/relative
 * path the engine recorded. Falls back to the bare filename.
 */
function shotUrl(rawPath) {
  if (!rawPath) return '';
  const norm = String(rawPath).replace(/\\/g, '/');
  const idx = norm.toLowerCase().lastIndexOf('/screenshots/');
  let rel;
  if (idx !== -1) {
    rel = norm.slice(idx + '/screenshots/'.length);
  } else if (norm.toLowerCase().startsWith('screenshots/')) {
    rel = norm.slice('screenshots/'.length);
  } else {
    rel = extractFilename(norm);
  }
  // Encode each segment but preserve the slashes
  const encoded = rel.split('/').map(encodeURIComponent).join('/');
  return `${API_BASE}/api/screenshot/${encoded}`;
}
function truncate(s, n) {
  return s && s.length > n ? s.slice(0, n - 1) + '…' : s;
}
function escapeHtml(s) {
  const d = document.createElement('div');
  d.textContent = String(s ?? '');
  return d.innerHTML;
}
function escapeAttr(s) {
  return escapeHtml(s).replace(/"/g, '&quot;');
}
