/**
 * FINN - Financial Investment Agent
 * Mobile-First Client Application Logic
 */

// Application State
const state = {
  currentTab: 'pushView',
  windowHours: 24,
  currentFilter: 'all',
  selectedTicker: 'TCS',
  activeModule: 'narrative_vs_numbers',
  portfolioCompanies: [],
  activeAlerts: [],
  digestData: null,
  researchData: {},
  isFullWidth: false,
};

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', async () => {
  initLucide();
  setupNavigation();
  setupEventListeners();

  // Initial Data Fetch
  await loadPortfolio();
  await loadPushDigest();
  await loadActiveAlerts();
  await loadResearch(state.selectedTicker);
  await loadCostAudit();
});

function initLucide() {
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

// ── Navigation & Event Bindings ─────────────────────────────────────────────

function setupNavigation() {
  const navBtns = document.querySelectorAll('.nav-btn');
  navBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetTab = btn.getAttribute('data-tab');
      switchTab(targetTab);
    });
  });

  // Module Tabs in Pull View
  const moduleTabs = document.querySelectorAll('.module-tab');
  moduleTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const mod = tab.getAttribute('data-module');
      switchModule(mod);
    });
  });

  // Time Window Selectors
  const windowBtns = document.querySelectorAll('.window-btn');
  windowBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      windowBtns.forEach(b => {
        b.className = 'window-btn px-2.5 py-1 rounded-md font-medium text-slate-400 hover:text-white';
      });
      btn.className = 'window-btn px-2.5 py-1 rounded-md font-medium text-white bg-amber-500/20 text-amber-300';
      state.windowHours = parseInt(btn.getAttribute('data-window'), 10);
      loadPushDigest();
    });
  });

  // Category Filter Chips
  const filterChips = document.querySelectorAll('.filter-chip');
  filterChips.forEach(chip => {
    chip.addEventListener('click', () => {
      filterChips.forEach(c => {
        c.className = 'filter-chip px-2.5 py-1 rounded-full bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white whitespace-nowrap';
      });
      chip.className = 'filter-chip px-2.5 py-1 rounded-full bg-white/10 text-white font-medium whitespace-nowrap';
      state.currentFilter = chip.getAttribute('data-filter');
      renderAnnouncementFeed();
    });
  });

  // Quick Ticker Chips
  const tickerChips = document.querySelectorAll('.ticker-chip');
  tickerChips.forEach(chip => {
    chip.addEventListener('click', () => {
      const ticker = chip.getAttribute('data-ticker');
      selectTicker(ticker);
    });
  });
}

function setupEventListeners() {
  // Viewport Mode Toggle (Mobile / Desktop Frame)
  const viewportBtn = document.getElementById('viewportToggleBtn');
  viewportBtn.addEventListener('click', () => {
    state.isFullWidth = !state.isFullWidth;
    document.body.classList.toggle('full-viewport-mode', state.isFullWidth);
    viewportBtn.innerHTML = state.isFullWidth 
      ? '<i data-lucide="minimize-2" class="w-4 h-4"></i>'
      : '<i data-lucide="smartphone" class="w-4 h-4"></i>';
    initLucide();
  });

  // Ticker Search
  const searchInput = document.getElementById('tickerSearchInput');
  const searchBtn = document.getElementById('executeSearchBtn');
  const performSearch = () => {
    const val = searchInput.value.trim().toUpperCase();
    if (val) {
      selectTicker(val);
    }
  };
  searchBtn.addEventListener('click', performSearch);
  searchInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') performSearch();
  });

  // Paperwork Accordion Toggle
  const togglePaperworkBtn = document.getElementById('togglePaperworkBtn');
  const paperworkList = document.getElementById('paperworkList');
  togglePaperworkBtn.addEventListener('click', () => {
    paperworkList.classList.toggle('hidden');
  });

  // Alert Sliders
  const priceSlider = document.getElementById('priceSlider');
  const volumeSlider = document.getElementById('volumeSlider');
  priceSlider.addEventListener('input', (e) => {
    document.getElementById('priceThresholdVal').textContent = `±${parseFloat(e.target.value).toFixed(1)}%`;
  });
  volumeSlider.addEventListener('input', (e) => {
    document.getElementById('volumeThresholdVal').textContent = `${parseFloat(e.target.value).toFixed(1)}x`;
  });

  // Save Alert Configs
  document.getElementById('saveAlertConfigsBtn').addEventListener('click', async () => {
    await saveAlertPreferences();
  });

  // Re-evaluate EOD Button
  document.getElementById('refreshEodBtn').addEventListener('click', async () => {
    try {
      await fetch('/api/push/refresh', { method: 'POST' });
      await loadActiveAlerts();
      await loadPushDigest();
      alert('EOD price moves and filings re-evaluated.');
    } catch (e) {
      console.error(e);
    }
  });

  // Top Alert Dismiss
  document.getElementById('dismissTopAlertBtn').addEventListener('click', () => {
    document.getElementById('topAlertBanner').classList.add('hidden');
  });
}

function switchTab(tabId) {
  state.currentTab = tabId;
  const sections = ['pushView', 'pullView', 'portfolioView', 'alertsView'];
  sections.forEach(s => {
    const el = document.getElementById(s);
    if (el) el.classList.toggle('hidden', s !== tabId);
  });

  const navBtns = document.querySelectorAll('.nav-btn');
  navBtns.forEach(btn => {
    const active = btn.getAttribute('data-tab') === tabId;
    btn.classList.toggle('active', active);
    btn.classList.toggle('text-amber-400', active);
    btn.classList.toggle('text-slate-400', !active);
  });

  initLucide();
}

function switchModule(moduleName) {
  state.activeModule = moduleName;
  const moduleTabs = document.querySelectorAll('.module-tab');
  moduleTabs.forEach(tab => {
    const active = tab.getAttribute('data-module') === moduleName;
    tab.className = active
      ? 'module-tab pb-2 font-semibold text-amber-400 border-b-2 border-amber-400 whitespace-nowrap flex items-center space-x-1'
      : 'module-tab pb-2 font-medium text-slate-400 hover:text-white whitespace-nowrap';
  });

  renderModuleContent();
}

// ── PUSH MODE LOGIC (Windowed Digest) ───────────────────────────────────────

async function loadPushDigest() {
  const feed = document.getElementById('announcementFeed');
  feed.innerHTML = '<div class="text-center py-6 text-slate-500 text-xs">Fetching windowed corporate filings...</div>';

  try {
    const res = await fetch(`/api/push/digest?hours=${state.windowHours}`);
    const data = await res.json();
    state.digestData = data;

    // Render Stats & Executive Summary
    document.getElementById('digestMetaStats').textContent = `${data.total} Filings | ${data.window}`;
    document.getElementById('digestSummaryText').textContent = data.summary || 'No material corporate filings within this window.';

    renderAnnouncementFeed();
  } catch (err) {
    feed.innerHTML = `<div class="text-center py-6 text-red-400 text-xs">Error loading filings: ${err.message}</div>`;
  }
}

function renderAnnouncementFeed() {
  const feed = document.getElementById('announcementFeed');
  if (!state.digestData) return;

  const { high = [], medium = [], low = [], skipped = 0 } = state.digestData;
  let allItems = [...high, ...medium, ...low];

  // Apply Filter Chip
  if (state.currentFilter !== 'all') {
    allItems = allItems.filter(item => {
      if (state.currentFilter === 'results') return item.category === 'results';
      if (state.currentFilter === 'management_change') return item.category === 'management_change';
      if (state.currentFilter === 'M&A') return item.category === 'M&A';
      if (state.currentFilter === 'litigation') return item.category === 'litigation';
      return true;
    });
  }

  if (allItems.length === 0) {
    feed.innerHTML = '<div class="text-center py-8 text-slate-500 text-xs">No corporate announcements matching this filter.</div>';
    return;
  }

  feed.innerHTML = allItems.map(item => renderAnnouncementCard(item)).join('');

  // Handle collapsed paperwork
  const collapsedBox = document.getElementById('collapsedPaperwork');
  const countText = document.getElementById('collapsedCountText');
  if (skipped > 0) {
    collapsedBox.classList.remove('hidden');
    countText.textContent = `Routine Administrative Paperwork (${skipped} filings collapsed)`;
  } else {
    collapsedBox.classList.add('hidden');
  }

  initLucide();
}

function renderAnnouncementCard(item) {
  const isHigh = item.priority === 'HIGH';
  const badgeClass = isHigh ? 'badge-high' : (item.priority === 'MEDIUM' ? 'badge-med' : 'badge-low');

  // Format timestamp
  const dateStr = item.filed_at ? new Date(item.filed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', month: 'short', day: 'numeric' }) : '';

  // Results Structured Table
  let enrichmentHtml = '';
  if (item.category === 'results' && item.enrichment) {
    const en = item.enrichment;
    enrichmentHtml = `
      <div class="mt-2.5 pt-2.5 border-t border-white/5">
        <span class="text-[10px] text-slate-400 uppercase font-semibold block mb-1.5">Headline Quarterly Results:</span>
        <div class="grid grid-cols-4 gap-1.5 text-center text-xs">
          <div class="p-1.5 rounded bg-slate-900/90 border border-white/5">
            <span class="text-[10px] text-slate-400 block">Revenue</span>
            <span class="font-bold mono text-white">₹${en.revenue?.value?.toLocaleString() || '-'} Cr</span>
            <span class="text-[9px] mono ${en.revenue?.yoy_pct >= 0 ? 'text-emerald-400' : 'text-red-400'} block">YoY ${en.revenue?.yoy_pct >= 0 ? '+' : ''}${en.revenue?.yoy_pct}%</span>
          </div>
          <div class="p-1.5 rounded bg-slate-900/90 border border-white/5">
            <span class="text-[10px] text-slate-400 block">EBITDA</span>
            <span class="font-bold mono text-white">₹${en.ebitda?.value?.toLocaleString() || '-'} Cr</span>
            <span class="text-[9px] mono ${en.ebitda?.yoy_pct >= 0 ? 'text-emerald-400' : 'text-red-400'} block">YoY ${en.ebitda?.yoy_pct >= 0 ? '+' : ''}${en.ebitda?.yoy_pct}%</span>
          </div>
          <div class="p-1.5 rounded bg-slate-900/90 border border-white/5">
            <span class="text-[10px] text-slate-400 block">PBT</span>
            <span class="font-bold mono text-white">₹${en.pbt?.value?.toLocaleString() || '-'} Cr</span>
            <span class="text-[9px] mono ${en.pbt?.yoy_pct >= 0 ? 'text-emerald-400' : 'text-red-400'} block">YoY ${en.pbt?.yoy_pct >= 0 ? '+' : ''}${en.pbt?.yoy_pct}%</span>
          </div>
          <div class="p-1.5 rounded bg-slate-900/90 border border-white/5">
            <span class="text-[10px] text-slate-400 block">PAT</span>
            <span class="font-bold mono text-white">₹${en.pat?.value?.toLocaleString() || '-'} Cr</span>
            <span class="text-[9px] mono ${en.pat?.yoy_pct >= 0 ? 'text-emerald-400' : 'text-red-400'} block">YoY ${en.pat?.yoy_pct >= 0 ? '+' : ''}${en.pat?.yoy_pct}%</span>
          </div>
        </div>
      </div>
    `;
  } else if (item.category === 'management_change' && item.enrichment) {
    const en = item.enrichment;
    enrichmentHtml = `
      <div class="mt-2.5 p-2 rounded-lg bg-amber-500/5 border border-amber-500/20 text-xs space-y-1">
        <div class="flex items-center justify-between font-semibold">
          <span class="text-white">${en.person_name || 'Senior Executive'}</span>
          <span class="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 uppercase">${en.action || 'Appointment'}</span>
        </div>
        <p class="text-slate-300 text-[11px]">${en.role}</p>
        <p class="text-slate-400 text-[11px] italic">"${en.background}"</p>
      </div>
    `;
  }

  return `
    <div class="glass-card p-3.5 space-y-2 ${isHigh ? 'highlight' : ''}">
      <div class="flex items-start justify-between">
        <div class="flex items-center space-x-2">
          <button onclick="selectTicker('${item.ticker}')" class="text-xs font-bold mono px-2 py-0.5 rounded bg-slate-800 hover:bg-amber-500 hover:text-slate-950 transition-colors text-white border border-white/10">
            ${item.ticker}
          </button>
          <span class="badge ${badgeClass}">${item.category?.toUpperCase()}</span>
        </div>
        <span class="text-[10px] text-slate-500 mono">${dateStr}</span>
      </div>

      <p class="text-xs font-medium text-slate-200 leading-snug">
        ${item.ai_summary || item.subject}
      </p>

      ${enrichmentHtml}

      <div class="pt-1 flex items-center justify-between text-[11px] text-slate-400">
        <span class="truncate max-w-[200px]">${item.company_name}</span>
        ${item.attachment_url ? `
          <a href="${item.attachment_url}" target="_blank" rel="noopener noreferrer" class="text-amber-400 hover:underline flex items-center space-x-1 shrink-0">
            <span>Exchange Filing</span>
            <i data-lucide="external-link" class="w-3 h-3"></i>
          </a>
        ` : ''}
      </div>
    </div>
  `;
}

// ── PULL MODE LOGIC (Deep Research) ─────────────────────────────────────────

async function selectTicker(ticker) {
  state.selectedTicker = ticker.toUpperCase();
  document.getElementById('tickerSearchInput').value = state.selectedTicker;

  // Update Header UI
  document.getElementById('targetTicker').textContent = state.selectedTicker;

  // Switch to pull view if not already
  if (state.currentTab !== 'pullView') {
    switchTab('pullView');
  }

  await loadResearch(state.selectedTicker);
}

async function loadResearch(ticker) {
  const container = document.getElementById('moduleContentArea');
  container.innerHTML = '<div class="text-center py-10 text-slate-500 text-xs">Synthesizing primary filings for ' + ticker + '...</div>';

  try {
    const res = await fetch(`/api/pull/research/${ticker}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.researchData[ticker] = data.report || {};

    // Update Company Header info
    document.getElementById('targetName').textContent = data.company_name || ticker;
    document.getElementById('targetSector').textContent = data.sector || 'Equities';

    // Update Provenance footer
    const citations = data.report?.narrative_vs_numbers?.primary_source_citations || [
      `${ticker} FY24 Annual Report & Recent Concall Transcripts`
    ];
    document.getElementById('citationsText').textContent = citations.join(' | ');

    renderModuleContent();
  } catch (err) {
    container.innerHTML = `<div class="text-center py-10 text-red-400 text-xs">Unable to load research for ${ticker}: ${err.message}</div>`;
  }
}

function renderModuleContent() {
  const container = document.getElementById('moduleContentArea');
  const report = state.researchData[state.selectedTicker];

  if (!report) {
    container.innerHTML = '<div class="text-center py-8 text-slate-500 text-xs">No analysis available.</div>';
    return;
  }

  const modData = report[state.activeModule];
  if (!modData) {
    container.innerHTML = '<div class="text-center py-8 text-slate-500 text-xs">Module not populated.</div>';
    return;
  }

  switch (state.activeModule) {
    case 'narrative_vs_numbers':
      container.innerHTML = renderNarrativeVsNumbers(modData);
      break;
    case 'financial_snapshot':
      container.innerHTML = renderFinancialSnapshot(modData);
      break;
    case 'business_snapshot':
      container.innerHTML = renderBusinessSnapshot(modData);
      break;
    case 'trajectory':
      container.innerHTML = renderTrajectory(modData);
      break;
    case 'balance_sheet':
      container.innerHTML = renderBalanceSheet(modData);
      break;
    case 'cash_quality':
      container.innerHTML = renderCashQuality(modData);
      break;
    case 'guidance':
      container.innerHTML = renderGuidance(modData);
      break;
    case 'bull_vs_bear':
      container.innerHTML = renderBullVsBear(modData);
      break;
    default:
      container.innerHTML = `<pre class="text-xs text-slate-300 p-3 bg-slate-900 rounded-lg overflow-x-auto">${JSON.stringify(modData, null, 2)}</pre>`;
  }

  initLucide();
}

// ── 8 Research Module Renderers ─────────────────────────────────────────────

function renderNarrativeVsNumbers(data) {
  const quarters = data.quarters || [];
  return `
    <div class="space-y-3">
      <!-- Credibility Hero Card -->
      <div class="glass-card highlight p-4 space-y-2">
        <div class="flex items-center justify-between">
          <span class="text-xs font-semibold text-amber-400 uppercase tracking-wider">Management Credibility Audit</span>
          <div class="flex items-center space-x-1.5">
            <span class="text-xs mono font-bold text-white">${data.delivery_rate_pct}% Accuracy</span>
            <span class="badge ${data.credibility_score === 'HIGH' ? 'badge-hit' : 'badge-miss'}">${data.credibility_score} CREDIBILITY</span>
          </div>
        </div>
        <p class="text-xs text-slate-200 leading-relaxed font-medium">
          ${data.executive_summary || ''}
        </p>
      </div>

      <!-- 4-Quarter Scorecard -->
      <div class="space-y-2">
        <span class="text-xs font-semibold text-slate-400 uppercase tracking-wider block">4-Quarter Delivery Scorecard</span>
        ${quarters.map(q => {
          const badgeType = q.verdict === 'HIT' ? 'badge-hit' : (q.verdict === 'MISS' ? 'badge-miss' : 'badge-inline');
          return `
            <div class="glass-card p-3 space-y-1.5">
              <div class="flex items-center justify-between">
                <div class="flex items-center space-x-2">
                  <span class="text-xs font-bold mono text-white px-1.5 py-0.5 rounded bg-slate-800">${q.quarter}</span>
                  <span class="text-xs text-slate-300 font-semibold">${q.metric}</span>
                </div>
                <span class="badge ${badgeType}">${q.verdict}</span>
              </div>
              <div class="grid grid-cols-2 gap-2 text-xs pt-1">
                <div class="p-2 rounded bg-slate-900/60 border border-white/5">
                  <span class="text-[10px] text-slate-400 block uppercase">Management Guided:</span>
                  <span class="text-slate-200 font-medium">${q.guided_statement}</span>
                </div>
                <div class="p-2 rounded bg-slate-900/60 border border-white/5">
                  <span class="text-[10px] text-slate-400 block uppercase">Delivered Actual:</span>
                  <span class="text-white font-bold mono">${q.delivered_actual}</span>
                </div>
              </div>
              <p class="text-[11px] text-slate-400 italic pt-0.5">${q.commentary || ''}</p>
            </div>
          `;
        }).join('')}
      </div>

      <!-- Verdict Banner -->
      <div class="p-3 rounded-lg bg-slate-900 border border-white/10 text-xs space-y-1">
        <span class="text-[10px] text-amber-400 font-bold uppercase tracking-wider block">ENAM Analyst Verdict:</span>
        <p class="text-slate-300">${data.credibility_verdict || ''}</p>
      </div>
    </div>
  `;
}

function renderFinancialSnapshot(data) {
  return `
    <div class="space-y-3">
      <div class="grid grid-cols-2 gap-2">
        <div class="glass-card p-3 text-center">
          <span class="text-[10px] text-slate-400 uppercase block">Annual Revenue</span>
          <span class="text-base font-bold mono text-white">₹${data.revenue?.toLocaleString()} Cr</span>
        </div>
        <div class="glass-card p-3 text-center">
          <span class="text-[10px] text-slate-400 uppercase block">Operating EBITDA</span>
          <span class="text-base font-bold mono text-white">₹${data.ebitda?.toLocaleString()} Cr</span>
          <span class="text-[10px] mono text-amber-400">${data.ebitda_margin_pct}% Margin</span>
        </div>
        <div class="glass-card p-3 text-center">
          <span class="text-[10px] text-slate-400 uppercase block">Net Profit (PAT)</span>
          <span class="text-base font-bold mono text-white">₹${data.pat?.toLocaleString()} Cr</span>
          <span class="text-[10px] mono text-slate-400">${data.pat_margin_pct}% Margin</span>
        </div>
        <div class="glass-card p-3 text-center">
          <span class="text-[10px] text-slate-400 uppercase block">Return on Equity (ROE)</span>
          <span class="text-base font-bold mono text-emerald-400">${data.roe_pct}%</span>
          <span class="text-[10px] mono text-slate-400">ROCE: ${data.roce_pct}%</span>
        </div>
      </div>

      <div class="glass-card p-3.5 space-y-2 text-xs">
        <div class="flex justify-between py-1 border-b border-white/5">
          <span class="text-slate-400">Valuation Multiples:</span>
          <span class="font-bold mono text-white">P/E ${data.pe_ratio}x</span>
        </div>
        <div class="flex justify-between py-1 border-b border-white/5">
          <span class="text-slate-400">Debt to Equity (D/E):</span>
          <span class="font-bold mono text-white">${data.debt_to_equity}x</span>
        </div>
        <div class="flex justify-between py-1">
          <span class="text-slate-400">Market Capitalization:</span>
          <span class="font-bold mono text-white">₹${data.market_cap_cr?.toLocaleString()} Cr</span>
        </div>
      </div>
    </div>
  `;
}

function renderBusinessSnapshot(data) {
  const segments = data.segments || [];
  return `
    <div class="space-y-3">
      <div class="glass-card p-3.5 space-y-1.5">
        <span class="text-xs font-semibold text-amber-400 uppercase tracking-wider block">Operating Model Overview</span>
        <p class="text-xs text-slate-200 leading-relaxed">${data.summary || ''}</p>
      </div>

      <div class="glass-card p-3.5 space-y-2">
        <span class="text-xs font-semibold text-slate-300 uppercase tracking-wider block">Segmental Revenue Contribution</span>
        <div class="space-y-2">
          ${segments.map(s => `
            <div class="space-y-1">
              <div class="flex justify-between text-xs">
                <span class="text-slate-200 font-medium">${s.name}</span>
                <span class="mono font-bold text-amber-400">${s.share_pct}%</span>
              </div>
              <div class="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                <div class="bg-amber-400 h-1.5 rounded-full" style="width: ${s.share_pct}%"></div>
              </div>
              <p class="text-[11px] text-slate-400">${s.description || ''}</p>
            </div>
          `).join('')}
        </div>
      </div>

      <div class="glass-card p-3.5 space-y-2">
        <span class="text-xs font-semibold text-slate-300 uppercase tracking-wider block">Structural Competitive Moats</span>
        <ul class="text-xs text-slate-300 space-y-1.5 list-disc pl-4">
          ${(data.competitive_moats || []).map(m => `<li>${m}</li>`).join('')}
        </ul>
      </div>
    </div>
  `;
}

function renderTrajectory(data) {
  return `
    <div class="space-y-3">
      <div class="grid grid-cols-2 gap-2 text-center text-xs">
        <div class="glass-card p-3">
          <span class="text-slate-400 text-[10px] uppercase block">3-Yr Revenue CAGR</span>
          <span class="text-base font-bold mono text-emerald-400">${data.revenue_cagr_3yr || '-'}</span>
        </div>
        <div class="glass-card p-3">
          <span class="text-slate-400 text-[10px] uppercase block">3-Yr EBITDA CAGR</span>
          <span class="text-base font-bold mono text-emerald-400">${data.ebitda_cagr_3yr || '-'}</span>
        </div>
      </div>

      <div class="glass-card p-3.5 space-y-2 text-xs">
        <span class="text-emerald-400 font-semibold uppercase block">Expanding Revenue Lines</span>
        <ul class="space-y-1 text-slate-300 list-disc pl-4">
          ${(data.growing_lines || []).map(l => `<li>${l}</li>`).join('')}
        </ul>
      </div>

      <div class="glass-card p-3.5 space-y-2 text-xs">
        <span class="text-red-400 font-semibold uppercase block">Compressing Segments & Headwinds</span>
        <ul class="space-y-1 text-slate-300 list-disc pl-4">
          ${(data.compressing_lines || []).map(l => `<li>${l}</li>`).join('')}
        </ul>
      </div>
    </div>
  `;
}

function renderBalanceSheet(data) {
  return `
    <div class="space-y-3">
      <div class="grid grid-cols-2 gap-2 text-center text-xs">
        <div class="glass-card p-3">
          <span class="text-slate-400 text-[10px] uppercase block">Gross Borrowings</span>
          <span class="text-base font-bold mono text-white">₹${data.gross_debt_cr?.toLocaleString() || '0'} Cr</span>
        </div>
        <div class="glass-card p-3">
          <span class="text-slate-400 text-[10px] uppercase block">Net Debt / Cash</span>
          <span class="text-base font-bold mono text-amber-400">₹${data.net_debt_cr?.toLocaleString() || '0'} Cr</span>
        </div>
      </div>

      <div class="glass-card p-3.5 space-y-2 text-xs">
        <span class="text-slate-300 font-semibold uppercase block">Working Capital Efficiency</span>
        <div class="grid grid-cols-3 gap-2 text-center py-1">
          <div class="p-2 rounded bg-slate-900 border border-white/5">
            <span class="text-[10px] text-slate-400 block">Debtor Days</span>
            <span class="font-bold mono text-white">${data.debtor_days || '-'} d</span>
          </div>
          <div class="p-2 rounded bg-slate-900 border border-white/5">
            <span class="text-[10px] text-slate-400 block">Inventory</span>
            <span class="font-bold mono text-white">${data.inventory_days || '-'} d</span>
          </div>
          <div class="p-2 rounded bg-slate-900 border border-white/5">
            <span class="text-[10px] text-slate-400 block">Working Capital</span>
            <span class="font-bold mono text-emerald-400">${data.working_capital_days || '-'} d</span>
          </div>
        </div>
        <p class="text-slate-300 text-[11px] pt-1">${data.capital_structure_verdict || ''}</p>
      </div>
    </div>
  `;
}

function renderCashQuality(data) {
  return `
    <div class="space-y-3">
      <div class="glass-card highlight p-4 text-center space-y-1">
        <span class="text-xs text-amber-400 font-semibold uppercase tracking-wider block">CFO to PAT Conversion Ratio</span>
        <div class="text-2xl font-bold mono text-white">${data.cfo_to_pat_conversion_pct}%</div>
        <span class="badge badge-hit">${data.cash_quality_score} QUALITY</span>
      </div>

      <div class="grid grid-cols-2 gap-2 text-center text-xs">
        <div class="glass-card p-3">
          <span class="text-slate-400 text-[10px] uppercase block">Cash from Operations (CFO)</span>
          <span class="text-base font-bold mono text-white">₹${data.cfo_cr?.toLocaleString()} Cr</span>
        </div>
        <div class="glass-card p-3">
          <span class="text-slate-400 text-[10px] uppercase block">Free Cash Flow (FCF)</span>
          <span class="text-base font-bold mono text-emerald-400">₹${data.free_cash_flow_cr?.toLocaleString()} Cr</span>
        </div>
      </div>

      <div class="glass-card p-3 text-xs space-y-1">
        <span class="text-slate-400 uppercase text-[10px] font-semibold block">Cash Conversion Verdict</span>
        <p class="text-slate-200 leading-relaxed">${data.conversion_verdict || ''}</p>
      </div>
    </div>
  `;
}

function renderGuidance(data) {
  return `
    <div class="space-y-3">
      <div class="glass-card highlight p-3.5 space-y-1.5">
        <span class="text-xs text-amber-400 font-semibold uppercase tracking-wider block">Forward Fiscal Targets</span>
        <div class="space-y-1 text-xs">
          <div class="flex justify-between py-1 border-b border-white/5">
            <span class="text-slate-400">Revenue Growth Guidance:</span>
            <span class="font-bold mono text-white">${data.revenue_growth_guidance || '-'}</span>
          </div>
          <div class="flex justify-between py-1 border-b border-white/5">
            <span class="text-slate-400">Target Margin Band:</span>
            <span class="font-bold mono text-white">${data.margin_guidance || '-'}</span>
          </div>
          <div class="flex justify-between py-1">
            <span class="text-slate-400">Capex Commitment:</span>
            <span class="font-bold mono text-white">${data.capex_plan || '-'}</span>
          </div>
        </div>
      </div>

      <div class="glass-card p-3.5 space-y-2 text-xs">
        <span class="text-slate-300 font-semibold uppercase block">Key Operational Milestones</span>
        <ul class="space-y-1 text-slate-300 list-disc pl-4">
          ${(data.strategic_initiatives || []).map(i => `<li>${i}</li>`).join('')}
        </ul>
      </div>
    </div>
  `;
}

function renderBullVsBear(data) {
  const bulls = data.bull_case || [];
  const bears = data.bear_case || [];
  return `
    <div class="space-y-3">
      <!-- Bull Case -->
      <div class="glass-card p-3.5 space-y-2 border-emerald-500/20 bg-emerald-500/5">
        <span class="text-xs font-bold text-emerald-400 uppercase flex items-center space-x-1">
          <i data-lucide="trending-up" class="w-3.5 h-3.5"></i>
          <span>High-Conviction Bull Case</span>
        </span>
        <div class="space-y-2 text-xs">
          ${bulls.map(b => `
            <div class="space-y-0.5">
              <span class="font-semibold text-white block">${b.pillar}</span>
              <p class="text-slate-300 text-[11px]">${b.driver}</p>
            </div>
          `).join('')}
        </div>
      </div>

      <!-- Bear Case -->
      <div class="glass-card p-3.5 space-y-2 border-red-500/20 bg-red-500/5">
        <span class="text-xs font-bold text-red-400 uppercase flex items-center space-x-1">
          <i data-lucide="trending-down" class="w-3.5 h-3.5"></i>
          <span>Key Structural Risks & Bear Case</span>
        </span>
        <div class="space-y-2 text-xs">
          ${bears.map(b => `
            <div class="space-y-0.5">
              <span class="font-semibold text-white block">${b.pillar}</span>
              <p class="text-slate-300 text-[11px]">${b.driver}</p>
            </div>
          `).join('')}
        </div>
      </div>
    </div>
  `;
}

// ── PORTFOLIO TAB LOGIC ─────────────────────────────────────────────────────

async function loadPortfolio() {
  try {
    const res = await fetch('/api/companies');
    const companies = await res.json();
    state.portfolioCompanies = companies;

    const table = document.getElementById('portfolioTable');
    table.innerHTML = companies.map(c => `
      <div onclick="selectTicker('${c.ticker}')" class="glass-card p-3 flex items-center justify-between cursor-pointer hover:border-amber-500/40 transition-all">
        <div>
          <div class="flex items-center space-x-2">
            <span class="text-xs font-bold mono text-white">${c.ticker}</span>
            <span class="text-[10px] text-slate-400 px-1.5 py-0.2 rounded bg-slate-800">${c.sector}</span>
          </div>
          <p class="text-[11px] text-slate-400 truncate max-w-[180px]">${c.name}</p>
        </div>
        <div class="text-right">
          <span class="text-xs font-bold mono text-white block">₹${c.close?.toLocaleString() || '-'}</span>
          <span class="text-[11px] mono font-semibold ${c.daily_change_pct >= 0 ? 'text-emerald-400' : 'text-red-400'}">
            ${c.daily_change_pct >= 0 ? '+' : ''}${c.daily_change_pct?.toFixed(2)}%
          </span>
        </div>
      </div>
    `).join('');
  } catch (err) {
    console.error('Error loading portfolio:', err);
  }
}

// ── ALERTS TAB LOGIC ────────────────────────────────────────────────────────

async function loadActiveAlerts() {
  try {
    const res = await fetch('/api/push/alerts');
    const alerts = await res.json();
    state.activeAlerts = alerts;

    // Update unread badge in header
    const badge = document.getElementById('unreadAlertBadge');
    if (alerts.length > 0) {
      badge.textContent = alerts.length;
      badge.classList.remove('hidden');

      // Update Top Ribbon with first alert
      document.getElementById('topAlertBanner').classList.remove('hidden');
      document.getElementById('topAlertText').textContent = alerts[0].title;
    } else {
      badge.classList.add('hidden');
      document.getElementById('topAlertBanner').classList.add('hidden');
    }

    const list = document.getElementById('alertsFeedList');
    if (alerts.length === 0) {
      list.innerHTML = '<div class="text-center py-6 text-slate-500 text-xs">No active threshold breaches. All parameters within configured limits.</div>';
      return;
    }

    list.innerHTML = alerts.map(a => `
      <div class="glass-card p-3 space-y-1.5 border-amber-500/20">
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-2">
            <span class="text-xs font-bold mono text-white px-1.5 py-0.5 rounded bg-slate-800">${a.company_ticker}</span>
            <span class="badge ${a.severity === 'HIGH' ? 'badge-high' : 'badge-med'}">${a.alert_type?.toUpperCase()}</span>
          </div>
          <button onclick="dismissAlert(${a.id})" class="text-[10px] text-slate-400 hover:text-white px-2 py-0.5 rounded bg-white/5">Dismiss</button>
        </div>
        <p class="text-xs text-slate-200 font-semibold">${a.title}</p>
        <p class="text-[11px] text-slate-400">${a.detail || ''}</p>
      </div>
    `).join('');

    initLucide();
  } catch (err) {
    console.error('Error loading alerts:', err);
  }
}

async function dismissAlert(alertId) {
  try {
    await fetch(`/api/push/alerts/${alertId}/dismiss`, { method: 'POST' });
    await loadActiveAlerts();
  } catch (err) {
    console.error('Error dismissing alert:', err);
  }
}

async function saveAlertPreferences() {
  const pVal = parseFloat(document.getElementById('priceSlider').value);
  const vVal = parseFloat(document.getElementById('volumeSlider').value);

  try {
    await fetch('/api/push/alert-configs/1', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ threshold: pVal })
    });
    await fetch('/api/push/alert-configs/2', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ threshold: vVal })
    });
    alert('Alert thresholds updated successfully.');
  } catch (e) {
    console.error(e);
  }
}

async function loadCostAudit() {
  try {
    const res = await fetch('/api/audit/costs');
    const data = await res.json();
    document.getElementById('costDisplay').textContent = `$${data.total_cost_usd?.toFixed(4)}`;
    document.getElementById('auditTotalCost').textContent = `$${data.total_cost_usd?.toFixed(6)}`;
    document.getElementById('auditTotalTokens').textContent = data.total_tokens?.toLocaleString() || '0';
  } catch (e) {
    console.error(e);
  }
}

