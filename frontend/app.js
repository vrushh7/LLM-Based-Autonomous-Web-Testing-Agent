/* ============================================================
   AI Browser Agent — Frontend v5.0
   Aligned with main.py response shapes:
     POST /api/test      → { success, report: { success, status, steps, duration,
                              summary: { passed_steps, total_steps, failed_steps },
                              instruction, test_id, timestamp },
                            test_plan, plan_source, bypassed_llm, llm_repaired,
                            validation_issues, execution_summary, test_folder }
     GET  /api/history   → { success, count, history: [...] }
     GET  /api/report/:id→ { success, report }
     GET  /health        → { status, llm_available, rag_stats, message }
   ============================================================ */

const API_BASE = (() => {
  const o = window.location.origin;
  return (o.includes('localhost') || o.includes('127.0.0.1'))
    ? 'http://localhost:8000'
    : o;
})();

/* ── State ──────────────────────────────────────────────────────────────── */
const state = {
  sessions:        [],
  activeSessionId: null,
  isRunning:       false,
  view:            'tests',
  history:         [],
  historyLoading:  false,
};

let sessionCounter = 0;
const newSessionId = () => `s${Date.now()}_${++sessionCounter}`;

/* ── DOM refs ───────────────────────────────────────────────────────────── */
const $ = (id) => document.getElementById(id);

const els = {
  healthDot:        $('healthDot'),
  healthText:       $('healthText'),
  themeToggle:      $('themeToggle'),
  navTabs:          document.querySelectorAll('.nav-tab'),
  views:            { tests: $('view-tests'), history: $('view-history') },

  sessionTabs:      $('sessionTabs'),
  newSessionBtn:    $('newSessionBtn'),
  sessionCountHint: $('sessionCountHint'),

  welcomeScreen:    $('welcomeScreen'),
  runningScreen:    $('runningScreen'),
  resultScreen:     $('resultScreen'),
  runningSub:       $('runningSub'),
  runningProgress:  $('runningProgress'),

  verdictBanner:    $('verdictBanner'),
  verdictIcon:      $('verdictIcon'),
  verdictTitle:     $('verdictTitle'),
  verdictMeta:      $('verdictMeta'),
  resultInstruction:$('resultInstruction'),
  stepsList:        $('stepsList'),
  stepsCount:       $('stepsCount'),
  shotsGrid:        $('shotsGrid'),
  shotsCount:       $('shotsCount'),
  downloadsSection: $('downloadsSection'),
  productsSection:  $('productsSection'),
  deleteSessionBtn: $('deleteSessionBtn'),

  instructionInput: $('instructionInput'),
  urlInput:         $('urlInput'),
  forceFreshToggle: $('forceFreshToggle'),
  micBtn:           $('micBtn'),
  runBtn:           $('runBtn'),
  exampleChips:     document.querySelectorAll('.example-chip'),

  historyList:         $('historyList'),
  refreshHistoryBtn:   $('refreshHistoryBtn'),
  toastContainer:      $('toastContainer'),
  lightbox:            $('lightbox'),
  lightboxImg:         $('lightboxImg'),
  lightboxClose:       $('lightboxClose'),
};

/* ── SVG fallback for broken screenshots ───────────────────────────────── */
const SVG_FALLBACK = (() => {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400">
    <rect width="100%" height="100%" fill="#111"/>
    <text x="300" y="210" fill="#888" font-size="18" font-family="monospace"
          text-anchor="middle">Screenshot unavailable</text>
  </svg>`;
  return 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(svg);
})();

/* ── Init ───────────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  attachListeners();
  addExtraExampleChips();
  pingHealth();
  setInterval(pingHealth, 15000);
  loadHistory();
  renderSessionTabs();
  showWelcome();
});

/* ── Theme ──────────────────────────────────────────────────────────────── */
function initTheme() {
  const saved = localStorage.getItem('theme') || 'dark';
  document.documentElement.setAttribute('data-theme', saved);
}
function toggleTheme() {
  const cur  = document.documentElement.getAttribute('data-theme');
  const next = cur === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
}

/* ── Extra example chips for all 8 requirements ─────────────────────────── */
function addExtraExampleChips() {
  const grid = document.querySelector('.example-grid');
  if (!grid) return;
  const extras = [
    { tag:'MONITOR', text:'Monitor Bitcoin, notify if below $50k',
      prompt:'Monitor Bitcoin price, notify if below $50,000' },
    { tag:'FLIGHTS', text:'Compare flights DEL→BOM, find cheapest',
      prompt:'Compare flights from DEL to BOM, show cheapest option' },
    { tag:'YOUTUBE', text:"Search YouTube 'lofi beats', play & like",
      prompt:"Search YouTube for lofi beats, play first video, like it" },
    { tag:'IMAGES',  text:'Google Images: sunset, download high-res',
      prompt:'Search Google Images for sunset, download high resolution image' },
    { tag:'STOCK',   text:'Monitor Tesla stock, buy if drops 5%',
      prompt:'Monitor Tesla stock, execute buy if price drops 5%' },
    { tag:'LOGIN',   text:'Smart login with test credentials',
      prompt:'Login with username testuser and password password123' },
  ];
  extras.forEach(ex => {
    const chip = document.createElement('button');
    chip.className = 'example-chip';
    chip.setAttribute('data-prompt', ex.prompt);
    chip.innerHTML = `<span class="chip-tag">${ex.tag}</span><span class="chip-text">${ex.text}</span>`;
    chip.addEventListener('click', () => {
      els.instructionInput.value = ex.prompt;
      els.instructionInput.focus();
    });
    grid.appendChild(chip);
  });
}

/* ── Event listeners ────────────────────────────────────────────────────── */
function attachListeners() {
  els.themeToggle.addEventListener('click', toggleTheme);
  els.navTabs.forEach(btn => btn.addEventListener('click', () => switchView(btn.dataset.view)));

  els.newSessionBtn.addEventListener('click', () => {
    state.activeSessionId = null;
    showWelcome();
    renderSessionTabs();
    els.instructionInput.focus();
  });

  els.runBtn.addEventListener('click', runTest);
  els.instructionInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); runTest(); }
  });

  els.exampleChips.forEach(chip => {
    chip.addEventListener('click', () => {
      els.instructionInput.value = chip.dataset.prompt;
      els.instructionInput.focus();
    });
  });

  els.deleteSessionBtn?.addEventListener('click', () => {
    if (state.activeSessionId) closeSession(state.activeSessionId);
  });

  els.refreshHistoryBtn.addEventListener('click', loadHistory);
  els.micBtn.addEventListener('click', toggleVoiceInput);

  els.lightboxClose.addEventListener('click', closeLightbox);
  els.lightbox.addEventListener('click', e => { if (e.target === els.lightbox) closeLightbox(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeLightbox(); });

  // Screenshot click → lightbox
  els.shotsGrid?.addEventListener('click', e => {
    const card = e.target.closest('.shot-card');
    if (card?.dataset.url) openLightbox(card.dataset.url);
  });

  // Downloads click
  els.downloadsSection?.addEventListener('click', e => {
    const card = e.target.closest('.shot-card');
    if (!card?.dataset.url) return;
    card.dataset.type === 'image' ? openLightbox(card.dataset.url) : window.open(card.dataset.url, '_blank');
  });
}

/* ── View switching ─────────────────────────────────────────────────────── */
function switchView(view) {
  state.view = view;
  els.navTabs.forEach(b => b.classList.toggle('active', b.dataset.view === view));
  Object.entries(els.views).forEach(([k, el]) => el?.classList.toggle('active', k === view));
  if (view === 'history') loadHistory();
}

/* ── Health ─────────────────────────────────────────────────────────────── */
async function pingHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`, { cache: 'no-store' });
    if (!res.ok) throw new Error();
    const data = await res.json();
    const online = data.status === 'healthy' || data.llm_available;
    setHealth(online ? 'online' : 'degraded', online ? 'ONLINE' : 'DEGRADED');
  } catch {
    setHealth('offline', 'OFFLINE');
  }
}
function setHealth(cls, text) {
  ['online', 'offline', 'degraded'].forEach(c => {
    els.healthDot.classList.remove(c);
    els.healthText.classList.remove(c);
  });
  els.healthDot.classList.add(cls);
  els.healthText.classList.add(cls);
  els.healthText.textContent = text;
}

/* ── Session model ──────────────────────────────────────────────────────── */
function createSession(instruction) {
  const id = newSessionId();
  const session = { id, name: shortName(instruction), instruction, status: 'running', payload: null };
  state.sessions.unshift(session);
  state.activeSessionId = id;
  renderSessionTabs();
  return session;
}
function getSession(id)      { return state.sessions.find(s => s.id === id); }
function closeSession(id) {
  const idx = state.sessions.findIndex(s => s.id === id);
  if (idx === -1) return;
  state.sessions.splice(idx, 1);
  if (state.activeSessionId === id) {
    const next = state.sessions[0];
    if (next) setActiveSession(next.id);
    else { state.activeSessionId = null; showWelcome(); }
  }
  renderSessionTabs();
}
function setActiveSession(id) {
  state.activeSessionId = id;
  renderSessionTabs();
  const s = getSession(id);
  if (!s)           { showWelcome(); return; }
  if (s.status === 'running') { showRunning(s.instruction); return; }
  if (s.payload)    renderSessionResult(s);
}
function shortName(instruction) {
  const words = instruction.replace(/[^\w\s]/g, '').trim().split(/\s+/).slice(0, 4).join(' ');
  return words.length > 32 ? words.slice(0, 32) + '…' : words || 'Test';
}

/* ── Session tabs ───────────────────────────────────────────────────────── */
function renderSessionTabs() {
  els.sessionTabs.innerHTML = '';
  state.sessions.forEach(s => {
    const tab = document.createElement('div');
    tab.className = 'session-tab' + (s.id === state.activeSessionId ? ' active' : '');
    tab.innerHTML = `
      <span class="tab-dot ${s.status}"></span>
      <span class="tab-name" title="${escapeAttr(s.instruction)}">${escapeHtml(s.name)}</span>
      <button class="tab-close" title="Close">×</button>
    `;
    tab.addEventListener('click', e => {
      if (e.target.classList.contains('tab-close')) { e.stopPropagation(); closeSession(s.id); }
      else setActiveSession(s.id);
    });
    els.sessionTabs.appendChild(tab);
  });
  if (els.sessionCountHint)
    els.sessionCountHint.textContent =
      `${state.sessions.length} active session${state.sessions.length === 1 ? '' : 's'}`;
}

/* ── Screens ────────────────────────────────────────────────────────────── */
function showWelcome() {
  els.welcomeScreen?.classList.remove('hidden');
  els.runningScreen?.classList.add('hidden');
  els.resultScreen?.classList.add('hidden');
}
function showRunning(instruction) {
  els.welcomeScreen?.classList.add('hidden');
  els.runningScreen?.classList.remove('hidden');
  els.resultScreen?.classList.add('hidden');
  if (els.runningSub) els.runningSub.textContent = truncate(instruction, 90);
  if (els.runningProgress) els.runningProgress.textContent = 'Running…';
}
function showResult() {
  els.welcomeScreen?.classList.add('hidden');
  els.runningScreen?.classList.add('hidden');
  els.resultScreen?.classList.remove('hidden');
}

/* ── Run test ───────────────────────────────────────────────────────────── */
async function runTest() {
  const instruction = els.instructionInput.value.trim();
  if (!instruction) { toast('Please enter an instruction', 'warning'); return; }
  if (state.isRunning) { toast('A test is already running', 'warning'); return; }

  const force_fresh = els.forceFreshToggle?.checked || false;
  const session = createSession(instruction);
  state.isRunning = true;
  setRunBtnLoading(true);
  showRunning(instruction);

  try {
    const res = await fetch(`${API_BASE}/api/test`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ instruction, force_fresh }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.error || `HTTP ${res.status}`);

    // main.py returns synchronous result (no exec_id polling needed)
    // Response shape: { success, report: { success, status, steps, duration,
    //   summary: {passed_steps, total_steps, failed_steps}, instruction,
    //   test_id, timestamp }, test_plan, plan_source, bypassed_llm,
    //   llm_repaired, validation_issues, execution_summary, test_folder }

    const report  = data.report || {};
    const passed  = !!report.success;

    session.status  = passed ? 'pass' : 'fail';
    session.payload = data;

    if (state.activeSessionId === session.id) renderSessionResult(session);
    renderSessionTabs();

    const sum = report.summary || {};
    toast(
      passed
        ? `✅ PASS · ${sum.passed_steps ?? 0}/${sum.total_steps ?? 0} steps`
        : `❌ FAIL · ${sum.failed_steps ?? 0} step(s) failed`,
      passed ? 'success' : 'error'
    );

    loadHistory();
    els.instructionInput.value = '';

  } catch (err) {
    session.status  = 'fail';
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
  els.runBtn.querySelector('.run-icon')?.classList.toggle('hidden', loading);
  els.runBtn.querySelector('.run-spinner')?.classList.toggle('hidden', !loading);
  const lbl = els.runBtn.querySelector('.run-label');
  if (lbl) lbl.textContent = loading ? 'Running…' : 'Run Test';
}

/* ── Render result ──────────────────────────────────────────────────────── */
function renderSessionResult(session) {
  const data   = session.payload;
  const report = data?.report;
  if (!report) { renderSessionError(session, 'No report returned from backend'); return; }

  clearDynamicSections();

  // ── Verdict banner ──
  const passed = !!report.success;
  els.verdictBanner.className = `verdict-banner ${passed ? 'pass' : 'fail'}`;
  els.verdictIcon.textContent  = passed ? '✓' : '✕';
  els.verdictTitle.textContent = passed ? 'PASS' : 'FAIL';

  // ── Meta line ──
  // report.summary = { passed_steps, total_steps, failed_steps }
  // data.execution_summary = { total, passed, failed } from automation_engine
  const sum  = report.summary || {};
  const esum = data.execution_summary || {};
  const dur  = report.duration != null ? `${Number(report.duration).toFixed(2)}s` : '—';
  const testId = report.test_id || '';

  els.verdictMeta.innerHTML = '';
  // Plan source badge
  if (data.plan_source) {
    const badge = document.createElement('span');
    badge.className = 'site-badge';
    badge.textContent = data.plan_source.replace('_', ' ').toUpperCase();
    els.verdictMeta.appendChild(badge);
    els.verdictMeta.appendChild(document.createTextNode(' '));
  }
  // Stats
  const passCount  = sum.passed_steps  ?? esum.passed  ?? 0;
  const totalCount = sum.total_steps   ?? esum.total   ?? 0;
  const failCount  = sum.failed_steps  ?? esum.failed  ?? 0;
  const bypassNote = data.bypassed_llm ? ' · ⚡ bypassed LLM' : '';
  const repairNote = data.llm_repaired ? ' · 🔧 auto-repaired' : '';

  els.verdictMeta.appendChild(document.createTextNode(
    `${passCount}/${totalCount} steps · ${dur}${bypassNote}${repairNote} · `
  ));
  if (testId) {
    const link = document.createElement('a');
    link.className  = 'report-link';
    link.href       = `${API_BASE}/api/report/${encodeURIComponent(testId)}/html`;
    link.target     = '_blank';
    link.rel        = 'noopener';
    link.textContent = `report ↗`;
    els.verdictMeta.appendChild(link);
  }

  // ── Instruction ──
  els.resultInstruction.textContent = report.instruction || session.instruction;

  // ── Validation issues ──
  renderValidationIssues(data.validation_issues);

  // ── Steps ──
  // report.steps comes from execution_result.steps (list of step log dicts)
  const steps = report.steps || [];
  renderSteps(steps);

  // ── Screenshots: pulled from step logs ──
  renderShots([], steps);

  // ── Downloads ──
  renderDownloads(data.downloads || []);

  // ── Extracted products ──
  renderExtractedProducts(data.extracted_products || []);

  // ── Monitoring triggers (from execution_summary variables) ──
  const monitorTriggers = data.execution_summary?.monitor_triggers
    || data.monitor_triggers
    || [];
  if (monitorTriggers.length) renderMonitoringTriggers(monitorTriggers);

  // ── Monitoring status ──
  const monitorStatus = data.execution_summary?.monitor_status
    || data.monitor_status
    || [];
  if (monitorStatus.length) renderMonitoringStatus(monitorStatus);

  // ── Flight results (stored in session variables by engine) ──
  const flightData = data.variables?.cheapest_flight || null;
  if (flightData) renderFlightResults(flightData);

  // ── YouTube step summary ──
  renderYouTubeInteractions(steps);

  showResult();
}

/* ── Clear dynamic sections between renders ─────────────────────────────── */
function clearDynamicSections() {
  ['monitoringSection', 'monitorStatusSection', 'flightSection',
   'youtubeSection', 'validationIssues'].forEach(id => $( id)?.remove());
}

/* ── Validation issues ──────────────────────────────────────────────────── */
function renderValidationIssues(issues) {
  if (!issues?.length) return;
  const node = document.createElement('div');
  node.id        = 'validationIssues';
  node.className = 'validation-issues';
  node.innerHTML = `
    <div class="vi-head">⚠️ Plan auto-repaired (${issues.length} issue${issues.length === 1 ? '' : 's'})</div>
    <ul class="vi-list">${issues.map(m => `<li>${escapeHtml(m)}</li>`).join('')}</ul>
  `;
  els.resultInstruction.insertAdjacentElement('afterend', node);
}

/* ── Steps ──────────────────────────────────────────────────────────────── */
function renderSteps(steps) {
  els.stepsList.innerHTML = '';
  if (els.stepsCount) els.stepsCount.textContent = steps.length;
  if (!steps.length) {
    els.stepsList.innerHTML = `<div class="empty-panel">No steps recorded</div>`;
    return;
  }
  steps.forEach(step => {
    // step shape from automation_engine execution_log:
    // { step, action, description, status, timestamp, screenshot, error, result }
    const ok    = step.status === 'success';
    const skip  = step.status === 'skipped';
    const cls   = ok ? 'pass' : skip ? 'skip' : 'fail';
    const label = ok ? 'PASS' : skip ? 'SKIP' : 'FAIL';

    const item = document.createElement('div');
    item.className = `step-item ${cls}`;

    // Extra detail rows for special actions
    let extras = '';
    if (step.action === 'youtube_search' && step.query)
      extras += `<div class="step-desc">🔍 ${escapeHtml(step.query)}</div>`;
    if (step.action === 'youtube_interact' && step.interaction)
      extras += `<div class="step-desc">▶ ${escapeHtml(step.interaction)}</div>`;
    if (step.action === 'search_images' && step.query)
      extras += `<div class="step-desc">🖼 ${escapeHtml(step.query)}</div>`;
    if (step.action === 'start_monitoring' && step.monitors)
      extras += `<div class="step-desc">📊 ${escapeHtml(JSON.stringify(step.monitors).slice(0, 120))}</div>`;
    if (step.action === 'compare_flights')
      extras += `<div class="step-desc">✈️ ${escapeHtml(step.origin||'?')} → ${escapeHtml(step.destination||'?')}</div>`;
    if (step.result)
      extras += `<div class="step-desc" style="color:var(--text-dim);font-size:11px">Result: ${escapeHtml(JSON.stringify(step.result).slice(0, 120))}</div>`;
    if (step.error)
      extras += `<div class="step-error">${escapeHtml(step.error)}</div>`;

    item.innerHTML = `
      <div class="step-num">${step.step ?? ''}</div>
      <div class="step-body">
        <div class="step-top">
          <span class="step-action">${escapeHtml(step.action || '')}</span>
        </div>
        <div class="step-desc">${escapeHtml(step.description || '')}</div>
        ${extras}
        ${step.screenshot ? `<div class="step-shot-name">📸 ${escapeHtml(extractFilename(step.screenshot))}</div>` : ''}
      </div>
      <div class="step-status ${cls}">${label}</div>
    `;
    els.stepsList.appendChild(item);
  });
}

/* ── Screenshots ────────────────────────────────────────────────────────── */
function renderShots(shots, steps) {
  els.shotsGrid.innerHTML = '';
  // Prefer step-level screenshots (always populated by automation_engine)
  const list = (steps || [])
    .filter(s => s.screenshot)
    .map(s => ({ path: s.screenshot, step: s.step, action: s.action }));

  // Fall back to explicit shots array
  const combined = list.length ? list : (shots || []).map(p =>
    typeof p === 'string' ? { path: p } : p
  );

  if (els.shotsCount) els.shotsCount.textContent = combined.length;
  if (!combined.length) {
    els.shotsGrid.innerHTML = `<div class="empty-panel">No screenshots captured</div>`;
    return;
  }

  combined.forEach(shot => {
    const raw   = shot.path || shot.filename || '';
    const url   = shotUrl(raw);
    if (!url) return;
    const label = shot.action
      ? `step_${shot.step}_${shot.action}`
      : extractFilename(raw);

    const card = document.createElement('div');
    card.className       = 'shot-card';
    card.dataset.url     = url;
    card.dataset.type    = 'image';
    card.innerHTML = `
      <img src="${url}" alt="${escapeAttr(label)}" loading="lazy"
           onerror="this.onerror=null;this.src='${SVG_FALLBACK}';this.parentElement.classList.add('shot-broken')" />
      <div class="shot-card-name" title="${escapeAttr(label)}">${escapeHtml(label)}</div>
    `;
    els.shotsGrid.appendChild(card);
  });
}

/* ── Downloads ──────────────────────────────────────────────────────────── */
function renderDownloads(downloads) {
  if (!els.downloadsSection) return;
  if (!downloads?.length) { els.downloadsSection.innerHTML = ''; return; }

  const isImage = fn => /\.(jpg|jpeg|png|gif|webp)$/i.test(fn);
  els.downloadsSection.innerHTML = `<h3 class="section-title">📥 Downloads (${downloads.length})</h3>`;
  const grid = document.createElement('div');
  grid.className = 'downloads-grid';

  downloads.forEach(dl => {
    const raw = typeof dl === 'string' ? dl : (dl.path || dl.filename || '');
    const fn  = typeof dl === 'string' ? extractFilename(dl) : (dl.filename || extractFilename(raw));
    const url = shotUrl(raw);

    const card = document.createElement('div');
    card.className = 'shot-card';
    if (isImage(fn) && url) {
      card.dataset.url  = url;
      card.dataset.type = 'image';
      card.innerHTML = `
        <img src="${url}" alt="${escapeAttr(fn)}" loading="lazy"
             onerror="this.onerror=null;this.src='${SVG_FALLBACK}';" />
        <div class="shot-card-name">${escapeHtml(fn)}</div>
      `;
    } else {
      card.dataset.url  = url || '';
      card.dataset.type = 'file';
      card.innerHTML = `
        <div style="padding:20px;text-align:center;font-size:2.5em">📄</div>
        <div class="shot-card-name">${escapeHtml(fn)}</div>
      `;
    }
    grid.appendChild(card);
  });
  els.downloadsSection.appendChild(grid);
}

/* ── Extracted products ─────────────────────────────────────────────────── */
function renderExtractedProducts(products) {
  if (!els.productsSection) return;
  if (!products?.length) { els.productsSection.innerHTML = ''; return; }

  els.productsSection.innerHTML =
    `<h3 class="section-title">🛒 Extracted Products (${products.length})</h3>`;
  const grid = document.createElement('div');
  grid.className = 'product-grid';

  products.slice(0, 12).forEach(p => {
    const card = document.createElement('div');
    card.className = 'product-card';
    // ProductOption fields: name, price, rating, reviews, url, platform, score
    card.innerHTML = `
      <div class="product-title">${escapeHtml((p.name || p.title || 'N/A').slice(0, 80))}</div>
      <div class="product-price">₹${escapeHtml(String(p.price || 'N/A'))}</div>
      ${p.rating  ? `<div class="product-rating">⭐ ${escapeHtml(String(p.rating))} ${p.reviews ? `(${escapeHtml(String(p.reviews))})` : ''}</div>` : ''}
      ${p.platform? `<div class="product-source">${escapeHtml(p.platform)}</div>` : ''}
      ${p.score   ? `<div style="font-size:11px;color:var(--text-dim)">Score: ${Number(p.score).toFixed(3)}</div>` : ''}
    `;
    if (p.url) {
      card.style.cursor = 'pointer';
      card.addEventListener('click', () => window.open(p.url, '_blank'));
    }
    grid.appendChild(card);
  });
  els.productsSection.appendChild(grid);
}

/* ── Monitoring triggers ────────────────────────────────────────────────── */
// triggers = MonitorManager.get_triggers() list:
// { monitor_id, item_id, value, threshold, condition, count, last_check }
function renderMonitoringTriggers(triggers) {
  if (!triggers?.length) return;
  const container = document.createElement('div');
  container.id        = 'monitoringSection';
  container.className = 'panel';
  container.style.marginBottom = '16px';
  container.innerHTML = `
    <header class="panel-head">
      <h4 class="panel-title">🔔 Monitoring Triggers (${triggers.length})</h4>
    </header>
    <div style="display:flex;flex-direction:column;gap:8px;">
      ${triggers.map(t => `
        <div style="background:var(--warn-soft,#2a2000);border-left:3px solid var(--warn,#f5a623);
                    padding:10px 12px;border-radius:8px;font-size:13px;">
          <strong>${escapeHtml(t.item_id || 'Unknown')}</strong> &nbsp;
          <span style="color:var(--text-dim)">${escapeHtml(t.condition)} ${escapeHtml(String(t.threshold))}</span><br>
          Current value: <strong style="color:#2ee8a5">${escapeHtml(String(t.value ?? '—'))}</strong> &nbsp;
          Triggered: <strong>${t.count ?? 0}</strong>×<br>
          <small style="color:var(--text-dim)">Last check: ${escapeHtml(t.last_check || '—')}</small>
        </div>
      `).join('')}
    </div>
  `;
  els.resultInstruction.insertAdjacentElement('afterend', container);
}

/* ── Monitoring status ──────────────────────────────────────────────────── */
// statuses = MonitorManager.get_status() list:
// { monitor_id, item_id, item_type, condition, threshold, last_value, trigger_count, active }
function renderMonitoringStatus(statuses) {
  if (!statuses?.length) return;
  const container = document.createElement('div');
  container.id        = 'monitorStatusSection';
  container.className = 'panel';
  container.style.marginBottom = '16px';
  container.innerHTML = `
    <header class="panel-head">
      <h4 class="panel-title">📊 Active Monitors (${statuses.length})</h4>
    </header>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:8px;">
      ${statuses.map(m => `
        <div style="background:var(--surface-2);padding:10px;border-radius:8px;font-size:12px;">
          <div style="font-weight:600">${escapeHtml(m.item_id)}</div>
          <div style="color:var(--text-dim)">${escapeHtml(m.item_type)} · ${escapeHtml(m.condition)} ${escapeHtml(String(m.threshold))}</div>
          <div>Last: <strong>${escapeHtml(String(m.last_value ?? '—'))}</strong></div>
          <div>Triggered: ${m.trigger_count ?? 0}× &nbsp;
               <span style="color:${m.active ? '#2ee8a5' : '#888'}">${m.active ? '● Active' : '○ Stopped'}</span>
          </div>
        </div>
      `).join('')}
    </div>
  `;
  const existing = $('monitoringSection');
  if (existing) existing.insertAdjacentElement('afterend', container);
  else els.resultInstruction.insertAdjacentElement('afterend', container);
}

/* ── Flight results ─────────────────────────────────────────────────────── */
// flightData = session.variables["cheapest_flight"] = { airline, price, ... }
function renderFlightResults(flightData) {
  if (!flightData) return;
  const container = document.createElement('div');
  container.id        = 'flightSection';
  container.className = 'panel';
  container.style.marginBottom = '16px';
  container.innerHTML = `
    <header class="panel-head">
      <h4 class="panel-title">✈️ Flight Result</h4>
    </header>
    <div style="background:var(--surface-2);padding:12px;border-radius:8px;">
      <strong>💰 Cheapest option</strong><br>
      Airline: <strong>${escapeHtml(String(flightData.airline || 'N/A'))}</strong><br>
      Price:   <strong style="color:#2ee8a5">₹${escapeHtml(String(flightData.price || 'N/A'))}</strong>
      ${flightData.duration ? `<br>Duration: ${escapeHtml(String(flightData.duration))}` : ''}
      ${flightData.stops != null ? `<br>Stops: ${flightData.stops}` : ''}
    </div>
  `;
  const existing = $('monitorStatusSection') || $('monitoringSection');
  if (existing) existing.insertAdjacentElement('afterend', container);
  else els.resultInstruction.insertAdjacentElement('afterend', container);
}

/* ── YouTube interaction summary ────────────────────────────────────────── */
function renderYouTubeInteractions(steps) {
  const ytSteps = steps.filter(s =>
    s.action === 'youtube_interact' || s.action === 'youtube_search'
  );
  if (!ytSteps.length) return;

  const container = document.createElement('div');
  container.id        = 'youtubeSection';
  container.className = 'panel';
  container.style.marginBottom = '16px';

  const icons = {
    like:'❤️', unlike:'💔', subscribe:'🔔', fullscreen:'🖥️',
    open_comments:'💬', scroll_comments:'📜', mute:'🔇', pause:'⏸', settings:'⚙️',
  };
  container.innerHTML = `
    <header class="panel-head">
      <h4 class="panel-title">🎬 YouTube Interactions</h4>
    </header>
    <div style="display:flex;gap:8px;flex-wrap:wrap;padding:4px 0;">
      ${ytSteps.map(s => {
        if (s.action === 'youtube_search')
          return `<span class="step-action">🔍 ${escapeHtml(s.query || 'search')}</span>`;
        const ic = icons[s.interaction] || '▶️';
        return `<span class="step-action">${ic} ${escapeHtml(s.interaction || s.action)}</span>`;
      }).join('')}
    </div>
  `;
  const existing = $('flightSection') || $('monitorStatusSection') || $('monitoringSection');
  if (existing) existing.insertAdjacentElement('afterend', container);
  else els.resultInstruction.insertAdjacentElement('afterend', container);
}

/* ── Error screen ───────────────────────────────────────────────────────── */
function renderSessionError(session, message) {
  clearDynamicSections();
  els.verdictBanner.className   = 'verdict-banner fail';
  els.verdictIcon.textContent   = '✕';
  els.verdictTitle.textContent  = 'ERROR';
  els.verdictMeta.textContent   = 'Backend error';
  els.resultInstruction.textContent = session.instruction;
  els.stepsList.innerHTML  = `<div class="empty-panel">${escapeHtml(message)}</div>`;
  if (els.stepsCount) els.stepsCount.textContent = '0';
  els.shotsGrid.innerHTML  = `<div class="empty-panel">No screenshots</div>`;
  if (els.shotsCount) els.shotsCount.textContent = '0';
  showResult();
}

/* ── History ────────────────────────────────────────────────────────────── */
async function loadHistory() {
  if (state.historyLoading) return;
  state.historyLoading = true;
  els.historyList.innerHTML = `<div class="empty-state">Loading…</div>`;
  try {
    const res  = await fetch(`${API_BASE}/api/history?limit=30`);
    const data = await res.json();
    state.history = data.history || [];
    renderHistory();
  } catch {
    els.historyList.innerHTML =
      `<div class="empty-state">Could not load history. Is the backend running?</div>`;
  } finally {
    state.historyLoading = false;
  }
}

function renderHistory() {
  if (!state.history.length) {
    els.historyList.innerHTML =
      `<div class="empty-state">No tests yet. Run your first test from the Tests tab.</div>`;
    return;
  }
  els.historyList.innerHTML = '';
  state.history.forEach(item => {
    const passed = item.status === 'PASS';
    const ts     = item.timestamp ? new Date(item.timestamp).toLocaleString() : '';
    const dur    = item.duration != null ? `${Number(item.duration).toFixed(2)}s` : '—';

    const card = document.createElement('div');
    card.className = `history-card ${passed ? 'pass' : 'fail'}`;
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
        <button class="history-action-btn" data-act="steps">📋 Steps</button>
        <button class="history-action-btn" data-act="shots">📸 Screenshots</button>
        <button class="history-action-btn" data-act="report">📄 Report</button>
        <button class="history-action-btn danger" data-act="delete">🗑 Delete</button>
      </div>
      <div class="history-expand hidden" data-expand></div>
    `;

    const expand = card.querySelector('[data-expand]');
    card.querySelectorAll('.history-action-btn').forEach(btn => {
      btn.addEventListener('click', async e => {
        e.stopPropagation();
        const act = btn.dataset.act;
        if (act === 'report')
          return window.open(`${API_BASE}/api/report/${encodeURIComponent(item.test_id)}/html`, '_blank');
        if (act === 'delete')
          return deleteReport(item.test_id);
        toggleHistoryExpand(item.test_id, expand, act);
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
    const res  = await fetch(`${API_BASE}/api/report/${encodeURIComponent(testId)}`);
    const data = await res.json();
    if (!data.success) throw new Error('Report not found');
    const report = data.report;

    if (mode === 'steps') {
      // report.execution.steps from report_generator, or report.steps from main.py report
      const steps = report.execution?.steps ?? report.steps ?? [];
      container.innerHTML = '';
      const wrap = document.createElement('div');
      wrap.className = 'steps-list';
      if (!steps.length) wrap.innerHTML = `<div class="empty-panel">No steps</div>`;
      steps.forEach(step => {
        const ok  = step.status === 'success';
        const cls = ok ? 'pass' : 'fail';
        const item = document.createElement('div');
        item.className = `step-item ${cls}`;
        item.innerHTML = `
          <div class="step-num">${step.step ?? ''}</div>
          <div class="step-body">
            <div class="step-top"><span class="step-action">${escapeHtml(step.action || '')}</span></div>
            <div class="step-desc">${escapeHtml(step.description || '')}</div>
            ${step.screenshot ? `<div class="step-shot-name">📸 ${escapeHtml(extractFilename(step.screenshot))}</div>` : ''}
            ${step.error ? `<div class="step-error">${escapeHtml(step.error)}</div>` : ''}
          </div>
          <div class="step-status ${cls}">${ok ? 'PASS' : 'FAIL'}</div>
        `;
        wrap.appendChild(item);
      });
      container.appendChild(wrap);

    } else if (mode === 'shots') {
      // Screenshots from step logs
      const steps = report.execution?.steps ?? report.steps ?? [];
      const list  = steps
        .filter(s => s.screenshot)
        .map(s => ({ path: s.screenshot, step: s.step, action: s.action }));

      container.innerHTML = '';
      const grid = document.createElement('div');
      grid.className = 'shots-grid';
      grid.addEventListener('click', e => {
        const card = e.target.closest('.shot-card');
        if (card?.dataset.url) openLightbox(card.dataset.url);
      });
      if (!list.length) {
        grid.innerHTML = `<div class="empty-panel">No screenshots</div>`;
      } else {
        list.forEach(shot => {
          const url   = shotUrl(shot.path || '');
          if (!url) return;
          const label = `step_${shot.step}_${shot.action || ''}`;
          const card  = document.createElement('div');
          card.className       = 'shot-card';
          card.dataset.url     = url;
          card.dataset.type    = 'image';
          card.innerHTML = `
            <img src="${url}" alt="${escapeAttr(label)}" loading="lazy"
                 onerror="this.onerror=null;this.src='${SVG_FALLBACK}';" />
            <div class="shot-card-name">${escapeHtml(label)}</div>
          `;
          grid.appendChild(card);
        });
      }
      container.appendChild(grid);
    }
  } catch (err) {
    container.innerHTML = `<div class="empty-panel">Failed: ${escapeHtml(err.message)}</div>`;
  }
}

async function deleteReport(testId) {
  if (!confirm(`Delete test ${testId}?`)) return;
  try {
    const res = await fetch(`${API_BASE}/api/report/${encodeURIComponent(testId)}`, { method: 'DELETE' });
    if (!res.ok && res.status !== 404 && res.status !== 405) throw new Error(`HTTP ${res.status}`);
    toast('Report deleted', 'success');
  } catch (err) {
    toast(`Removed from view (${err.message})`, 'warning');
  }
  state.history = state.history.filter(h => h.test_id !== testId);
  renderHistory();
}

/* ── Voice input ────────────────────────────────────────────────────────── */
let recognition = null;
let isRecording = false;
function toggleVoiceInput() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) { toast('Voice input not supported in this browser', 'warning'); return; }
  if (isRecording) { stopVoice(); return; }
  recognition = new SR();
  recognition.lang = 'en-US';
  recognition.interimResults = true;
  const base = els.instructionInput.value;
  recognition.onresult = e => {
    let t = '';
    for (let i = e.resultIndex; i < e.results.length; i++) t += e.results[i][0].transcript;
    els.instructionInput.value = (base ? base + ' ' : '') + t;
  };
  recognition.onerror = e => { toast(`Voice error: ${e.error}`, 'error'); stopVoice(); };
  recognition.onend   = () => stopVoice();
  try {
    recognition.start();
    isRecording = true;
    els.micBtn.classList.add('recording');
    toast('Listening…', 'info');
  } catch { toast('Could not start voice input', 'error'); }
}
function stopVoice() {
  try { recognition?.stop(); } catch {}
  isRecording = false;
  els.micBtn.classList.remove('recording');
}

/* ── Lightbox ───────────────────────────────────────────────────────────── */
function openLightbox(url) {
  els.lightboxImg.src = url;
  els.lightbox.classList.remove('hidden');
}
function closeLightbox() {
  els.lightbox.classList.add('hidden');
  els.lightboxImg.src = '';
}

/* ── Toasts ─────────────────────────────────────────────────────────────── */
function toast(message, type = 'info') {
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = message;
  t.addEventListener('click', () => t.remove());
  els.toastContainer.appendChild(t);
  const delay = type === 'error' ? 7000 : 4000;
  setTimeout(() => {
    t.style.transition = 'opacity 0.3s';
    t.style.opacity    = '0';
    setTimeout(() => t.remove(), 300);
  }, delay);
}

/* ── URL / path helpers ─────────────────────────────────────────────────── */
function shotUrl(rawPath) {
  if (!rawPath) return '';
  const p = String(rawPath).replace(/\\/g, '/');
  if (p.startsWith('http://') || p.startsWith('https://')) return p;
  if (p.startsWith('/api/screenshot')) return `${API_BASE}${p}`;
  // Windows absolute path e.g. C:/Users/.../screenshots/session_abc/step_1_navigate.png
  const filename = p.split('/').pop();
  if (!filename || filename.length < 4) return '';
  return `${API_BASE}/api/screenshot/${encodeURIComponent(filename)}`;
}

function extractFilename(p) {
  return String(p || '').replace(/\\/g, '/').split('/').pop();
}

function truncate(s, n) {
  return s && s.length > n ? s.slice(0, n - 1) + '…' : (s || '');
}

function escapeHtml(s) {
  const d = document.createElement('div');
  d.textContent = String(s ?? '');
  return d.innerHTML;
}

function escapeAttr(s) {
  return escapeHtml(s).replace(/"/g, '&quot;');
}