import Papa from 'papaparse';
import Chart from 'chart.js/auto';
import L from 'leaflet';
import { TRANSLATIONS } from './i18n.js';
import { findDistrictCoords } from './geo.js';
import { mountExplorer } from './explorer.jsx';

const GITHUB_RAW = 'https://raw.githubusercontent.com/pratap1997/mp-mla-lad-fundn/main';
const DATA_SOURCES = {
  fund: `${GITHUB_RAW}/UP_MLA_LAD_Fund_YearWise.csv`,
  raj:  `${GITHUB_RAW}/Rajasthan_RDPRWMS/MLA_LAD_Rajasthan_YearWise.csv`,
};

let lang = localStorage.getItem('nt_lang') || 'en';
let allRows = [];
let filtered = [];
let rajData = [];
let page = 1;
const PAGE_SIZE = 50;

let pieUtilChart = null;
let pieHouseChart = null;
let yearChart = null;
let districtChart = null;
let leafletMap = null;
let mapLayerGroup = null;
let activeMapState = 'ALL';

// ── Helpers ─────────────────────────────────────────────────
function fmt(v) {
  const n = parseFloat(v);
  return Number.isNaN(n) ? '—' : n.toLocaleString('en-IN', { maximumFractionDigits: 2 });
}

function num(v) {
  const n = parseFloat(v);
  return Number.isNaN(n) ? 0 : n;
}

function mlaSplit(raw) {
  const m = raw?.match(/^\d+\s+(.+)$/);
  return m ? m[1] : (raw || '');
}

function utilColor(pct) {
  if (pct >= 80) return '#059669';
  if (pct >= 50) return '#d97706';
  return '#dc2626';
}

async function fetchCSV(url) {
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const text = await res.text();
    const parsed = Papa.parse(text, { header: true, skipEmptyLines: true });
    return parsed.data || [];
  } catch (err) {
    console.warn('Failed to fetch CSV:', url, err);
    return [];
  }
}

// ── Language Toggle (English-first + Hindi) ─────────────────
function applyLanguage(nextLang) {
  lang = nextLang === 'hi' ? 'hi' : 'en';
  localStorage.setItem('nt_lang', lang);
  document.documentElement.lang = lang;
  const dict = TRANSLATIONS[lang];

  document.querySelectorAll('[data-i18n]').forEach(el => {
    const k = el.getAttribute('data-i18n');
    if (dict[k]) el.textContent = dict[k];
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const k = el.getAttribute('data-i18n-placeholder');
    if (dict[k]) el.setAttribute('placeholder', dict[k]);
  });

  const lbl = document.getElementById('lang-label');
  if (lbl) lbl.textContent = lang === 'en' ? 'हिंदी' : 'English';
}

// ── Filters & Table ─────────────────────────────────────────
function populateDistricts(rows) {
  const sel = document.getElementById('district-filter');
  if (!sel) return;
  const dists = Array.from(new Set(rows.map(r => (r['Nodal District'] || '').trim()).filter(Boolean))).sort();
  dists.forEach(d => {
    const opt = document.createElement('option');
    opt.value = d;
    opt.textContent = d;
    sel.appendChild(opt);
  });
}

function applyFilters() {
  const q = (document.getElementById('mla-search')?.value || '').toLowerCase();
  const year = document.getElementById('year-filter')?.value || '';
  const house = document.getElementById('house-filter')?.value || '';
  const distFilter = document.getElementById('district-filter')?.value || '';

  filtered = allRows.filter(row => {
    const mlaName = (row['MLA Name & Constituency'] || '').toLowerCase();
    const dist = (row['Nodal District'] || '').trim();
    const rowYear = row['Year Label'] || row['Financial Year'] || '';
    const rowHouse = row['House'] || '';

    if (q && !mlaName.includes(q) && !dist.toLowerCase().includes(q)) return false;
    if (year && !rowYear.includes(year)) return false;
    if (house && !rowHouse.includes(house)) return false;
    if (distFilter && dist !== distFilter) return false;
    return true;
  });

  page = 1;
  renderTable();
  updateRankings();
}

function renderTable() {
  const tbody = document.getElementById('mla-tbody');
  const meta = document.getElementById('table-meta');
  if (!tbody) return;

  if (!filtered.length) {
    tbody.innerHTML = '<tr><td colspan="9" class="loading-row">No matching records found.</td></tr>';
    if (meta) meta.textContent = '';
    renderPagination();
    return;
  }

  const start = (page - 1) * PAGE_SIZE;
  const slice = filtered.slice(start, start + PAGE_SIZE);

  tbody.innerHTML = slice.map((row, idx) => {
    const alloc = num(row['Allocated Funds (Lakhs)']);
    const sanc = num(row['Sanctioned Amount (Lakhs)']);
    const spent = num(row['Expenditure (Lakhs)']);
    const rem = num(row['Remaining Balance (Lakhs)']);
    const pct = alloc > 0 ? Math.min(100, (spent / alloc) * 100) : 0;
    const color = utilColor(pct);
    const house = row['House'] || '';
    const isVS = house.includes('Sabha');
    const year = row['Year Label'] || row['Financial Year'] || '';
    const name = mlaSplit(row['MLA Name & Constituency'] || '');
    const dist = row['Nodal District'] || '';

    return `<tr data-row-idx="${start + idx}">
      <td>
        <div class="mla-name">${name}</div>
        <div class="mla-area">${dist}</div>
      </td>
      <td><span class="house-badge ${isVS ? 'house-badge--vs' : 'house-badge--vp'}">${isVS ? 'Vidhan Sabha' : 'Vidhan Parishad'}</span></td>
      <td>${year}</td>
      <td>${dist}</td>
      <td class="num">₹${fmt(alloc)}</td>
      <td class="num">₹${fmt(sanc)}</td>
      <td class="num">₹${fmt(spent)}</td>
      <td class="num">₹${fmt(rem)}</td>
      <td class="num">
        <div class="util-bar-wrap">
          <div class="util-bar"><div class="util-bar-fill" style="width:${pct.toFixed(1)}%;background:${color}"></div></div>
          <span class="util-pct" style="color:${color}">${pct.toFixed(0)}%</span>
        </div>
      </td>
    </tr>`;
  }).join('');

  tbody.querySelectorAll('tr[data-row-idx]').forEach(tr => {
    tr.addEventListener('click', () => {
      const row = filtered[Number(tr.getAttribute('data-row-idx'))];
      if (row) openMlaModal(row);
    });
  });

  if (meta) {
    meta.textContent = `Showing ${start + 1}–${Math.min(start + PAGE_SIZE, filtered.length)} of ${filtered.length.toLocaleString()} records (click any row for MLA history)`;
  }
  renderPagination();
}

function renderPagination() {
  const existing = document.getElementById('pagination');
  if (existing) existing.remove();
  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  if (totalPages <= 1) return;

  const wrap = document.createElement('div');
  wrap.id = 'pagination';
  wrap.className = 'pagination-wrap';

  const addBtn = (label, pg, disabled, active = false) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = label;
    btn.disabled = disabled;
    btn.className = `page-btn${active ? ' is-active' : ''}`;
    btn.addEventListener('click', () => {
      page = pg;
      renderTable();
      document.getElementById('mla-data')?.scrollIntoView({ behavior: 'smooth' });
    });
    wrap.appendChild(btn);
  };

  addBtn('Prev', page - 1, page === 1);
  const startP = Math.max(1, page - 2);
  const endP = Math.min(totalPages, startP + 4);
  for (let p = startP; p <= endP; p++) addBtn(String(p), p, false, p === page);
  addBtn('Next', page + 1, page === totalPages);
  document.getElementById('table-meta')?.after(wrap);
}

// ── MLA Detail Modal ────────────────────────────────────────
function openMlaModal(row) {
  const modal = document.getElementById('mla-modal');
  const title = document.getElementById('modal-title');
  const body = document.getElementById('modal-body');
  if (!modal || !title || !body) return;

  const rawName = row['MLA Name & Constituency'] || '';
  const cleanName = mlaSplit(rawName);
  const history = allRows.filter(r => r['MLA Name & Constituency'] === rawName);

  title.textContent = cleanName;
  body.innerHTML = `
    <p><strong>District:</strong> ${row['Nodal District'] || '—'} | <strong>House:</strong> ${row['House'] || '—'}</p>
    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr><th>Year</th><th class="num">Allocated (L)</th><th class="num">Sanctioned (L)</th><th class="num">Spent (L)</th><th class="num">Remaining (L)</th></tr>
        </thead>
        <tbody>
          ${history.map(h => `<tr>
            <td>${h['Year Label'] || h['Financial Year'] || ''}</td>
            <td class="num">₹${fmt(h['Allocated Funds (Lakhs)'])}</td>
            <td class="num">₹${fmt(h['Sanctioned Amount (Lakhs)'])}</td>
            <td class="num">₹${fmt(h['Expenditure (Lakhs)'])}</td>
            <td class="num">₹${fmt(h['Remaining Balance (Lakhs)'])}</td>
          </tr>`).join('')}
        </tbody>
      </table>
    </div>
    <p><a href="https://github.com/pratap1997/mp-mla-lad-fundn/tree/main/Portal_Documents" target="_blank" rel="noopener noreferrer" style="color:var(--color-primary);font-weight:600">Browse Official DPR PDFs &amp; Guidelines on GitHub &rarr;</a></p>
  `;
  modal.hidden = false;
}

function setupModal() {
  const modal = document.getElementById('mla-modal');
  const close = () => { if (modal) modal.hidden = true; };
  document.getElementById('modal-close')?.addEventListener('click', close);
  document.getElementById('modal-backdrop')?.addEventListener('click', close);
  document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });
}

// ── Export Filtered CSV ─────────────────────────────────────
function exportFilteredCSV() {
  if (!filtered.length) return;
  const csv = Papa.unparse(filtered);
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'neta-tracker-filtered.csv';
  a.click();
  URL.revokeObjectURL(url);
}

// ── Rankings ────────────────────────────────────────────────
function updateRankings() {
  const byMLA = {};
  filtered.forEach(row => {
    const name = mlaSplit(row['MLA Name & Constituency'] || '');
    if (!name) return;
    if (!byMLA[name]) byMLA[name] = { name, dist: row['Nodal District'] || '', spent: 0, alloc: 0 };
    byMLA[name].spent += num(row['Expenditure (Lakhs)']);
    byMLA[name].alloc += num(row['Allocated Funds (Lakhs)']);
  });

  const arr = Object.values(byMLA).filter(m => m.alloc > 0);
  arr.forEach(m => { m.pct = (m.spent / m.alloc) * 100; });

  const topSpenders = [...arr].sort((a, b) => b.spent - a.spent).slice(0, 10);
  const lowUtil = [...arr].sort((a, b) => a.pct - b.pct).slice(0, 10);

  const renderList = (elId, items, valFn, cls) => {
    const el = document.getElementById(elId);
    if (!el) return;
    el.innerHTML = items.map((m, i) => `
      <div class="rank-item">
        <span class="rank-num">${i + 1}</span>
        <div class="rank-info">
          <div class="rank-name">${m.name}</div>
          <div class="rank-sub">${m.dist}</div>
        </div>
        <span class="rank-val ${cls}">${valFn(m)}</span>
      </div>`).join('');
  };

  renderList('top-spenders', topSpenders, m => `₹${fmt(m.spent)}L`, 'rank-val--green');
  renderList('low-spenders', lowUtil, m => `${m.pct.toFixed(1)}%`, 'rank-val--red');
}

// ── Chart.js (Pie + House Doughnut + Year Bar + District Bar) ─
function renderCharts(rows) {
  if (!rows.length) return;

  const totalSpent = rows.reduce((s, r) => s + num(r['Expenditure (Lakhs)']), 0) / 100;
  const totalRem = rows.reduce((s, r) => s + Math.max(0, num(r['Remaining Balance (Lakhs)'])), 0) / 100;

  pieUtilChart?.destroy();
  const pieEl = document.getElementById('pie-util-chart');
  if (pieEl) {
    pieUtilChart = new Chart(pieEl, {
      type: 'pie',
      data: {
        labels: ['Expenditure (Cr)', 'Remaining Balance (Cr)'],
        datasets: [{ data: [totalSpent.toFixed(1), totalRem.toFixed(1)], backgroundColor: ['#059669', '#e2e8f0'] }],
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } },
    });
  }

  const vsAlloc = rows.filter(r => (r['House'] || '').includes('Sabha')).reduce((s, r) => s + num(r['Allocated Funds (Lakhs)']), 0) / 100;
  const vpAlloc = rows.filter(r => (r['House'] || '').includes('Parishad')).reduce((s, r) => s + num(r['Allocated Funds (Lakhs)']), 0) / 100;

  pieHouseChart?.destroy();
  const houseEl = document.getElementById('pie-house-chart');
  if (houseEl) {
    pieHouseChart = new Chart(houseEl, {
      type: 'doughnut',
      data: {
        labels: ['Vidhan Sabha (MLA)', 'Vidhan Parishad (MLC)'],
        datasets: [{ data: [vsAlloc.toFixed(1), vpAlloc.toFixed(1)], backgroundColor: ['#1a4fa0', '#e8650a'] }],
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } },
    });
  }

  const years = ['2023-24', '2024-25', '2025-26', '2026-27'];
  const allocY = [], sancY = [], spentY = [];
  years.forEach(yr => {
    const sub = rows.filter(r => (r['Year Label'] || '').includes(yr));
    allocY.push((sub.reduce((s, r) => s + num(r['Allocated Funds (Lakhs)']), 0) / 100).toFixed(1));
    sancY.push((sub.reduce((s, r) => s + num(r['Sanctioned Amount (Lakhs)']), 0) / 100).toFixed(1));
    spentY.push((sub.reduce((s, r) => s + num(r['Expenditure (Lakhs)']), 0) / 100).toFixed(1));
  });

  yearChart?.destroy();
  const yearEl = document.getElementById('year-chart');
  if (yearEl) {
    yearChart = new Chart(yearEl, {
      type: 'bar',
      data: {
        labels: years,
        datasets: [
          { label: 'Allocated (Cr)', data: allocY, backgroundColor: '#1a4fa0' },
          { label: 'Sanctioned (Cr)', data: sancY, backgroundColor: '#d97706' },
          { label: 'Expenditure (Cr)', data: spentY, backgroundColor: '#059669' },
        ],
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } },
    });
  }

  const distMap = {};
  rows.forEach(r => {
    const d = (r['Nodal District'] || '').trim();
    if (!d) return;
    distMap[d] = (distMap[d] || 0) + num(r['Expenditure (Lakhs)']) / 100;
  });
  const top10 = Object.entries(distMap).sort((a, b) => b[1] - a[1]).slice(0, 10);

  districtChart?.destroy();
  const distEl = document.getElementById('district-chart');
  if (distEl) {
    districtChart = new Chart(distEl, {
      type: 'bar',
      data: {
        labels: top10.map(d => d[0]),
        datasets: [{ label: 'Expenditure (Cr)', data: top10.map(d => d[1].toFixed(1)), backgroundColor: '#2563eb' }],
      },
      options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } },
    });
  }
}

// ── Leaflet District Map (UP + Rajasthan) ───────────────────
function initMap() {
  const el = document.getElementById('district-map');
  if (!el || leafletMap) return;
  leafletMap = L.map(el).setView([26.8, 78.5], 6);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; OpenStreetMap &copy; CARTO',
    maxZoom: 12,
  }).addTo(leafletMap);
  mapLayerGroup = L.layerGroup().addTo(leafletMap);
}

function updateMap() {
  if (!leafletMap || !mapLayerGroup) return;
  mapLayerGroup.clearLayers();

  const agg = {};
  if (activeMapState === 'ALL' || activeMapState === 'UP') {
    allRows.forEach(r => {
      const d = (r['Nodal District'] || '').trim();
      if (!d) return;
      if (!agg[d]) agg[d] = { name: d, state: 'Uttar Pradesh', alloc: 0, spent: 0 };
      agg[d].alloc += num(r['Allocated Funds (Lakhs)']);
      agg[d].spent += num(r['Expenditure (Lakhs)']);
    });
  }
  if (activeMapState === 'ALL' || activeMapState === 'RAJ') {
    rajData.forEach(r => {
      const d = (r['district_filter'] || '').trim();
      if (!d || d.toLowerCase() === 'all') return;
      const key = `RAJ:${d}`;
      if (!agg[key]) agg[key] = { name: d, state: 'Rajasthan', alloc: 0, spent: 0 };
      agg[key].alloc += num(r['available_funds_lacs']);
      agg[key].spent += num(r['financial_sanction_lacs']);
    });
  }

  Object.values(agg).forEach(d => {
    const coords = findDistrictCoords(d.name);
    if (!coords) return;
    const pct = d.alloc > 0 ? Math.min(100, (d.spent / d.alloc) * 100) : 0;
    const color = utilColor(pct);
    const radius = Math.max(6, Math.min(18, Math.sqrt(d.alloc / 100) * 1.4));

    L.circleMarker(coords, {
      radius,
      color,
      fillColor: color,
      fillOpacity: 0.65,
      weight: 1.5,
    })
      .bindPopup(`<strong>${d.name}</strong> (${d.state})<br/>Allocated: ₹${(d.alloc / 100).toFixed(1)} Cr<br/>Spent/Sanctioned: ₹${(d.spent / 100).toFixed(1)} Cr<br/>Utilisation: ${pct.toFixed(1)}%`)
      .addTo(mapLayerGroup);
  });
}

// ── Graphify Relational Tree ────────────────────────────────
function renderGraphifyTree(rows) {
  const container = document.getElementById('graphify-tree');
  if (!container || !rows.length) return;

  const byHouse = {};
  rows.forEach(r => {
    const h = r['House'] || 'Other';
    const d = (r['Nodal District'] || 'Unknown').trim();
    if (!byHouse[h]) byHouse[h] = { alloc: 0, spent: 0, districts: {} };
    byHouse[h].alloc += num(r['Allocated Funds (Lakhs)']) / 100;
    byHouse[h].spent += num(r['Expenditure (Lakhs)']) / 100;
    if (!byHouse[h].districts[d]) byHouse[h].districts[d] = { alloc: 0, spent: 0, count: 0 };
    byHouse[h].districts[d].alloc += num(r['Allocated Funds (Lakhs)']) / 100;
    byHouse[h].districts[d].spent += num(r['Expenditure (Lakhs)']) / 100;
    byHouse[h].districts[d].count += 1;
  });

  container.innerHTML = Object.entries(byHouse).map(([house, hData]) => {
    const topDists = Object.entries(hData.districts).sort((a, b) => b[1].spent - a[1].spent).slice(0, 12);
    return `<details class="graphify-node" open>
      <summary><span>Uttar Pradesh &rarr; ${house}</span><span>Allocated ₹${hData.alloc.toFixed(0)} Cr | Spent ₹${hData.spent.toFixed(0)} Cr</span></summary>
      <div class="graphify-children">
        ${topDists.map(([dName, dd]) => `
          <div class="graphify-leaf">
            <span>${dName} (${dd.count} records)</span>
            <span>Allocated ₹${dd.alloc.toFixed(1)} Cr &bull; Spent ₹${dd.spent.toFixed(1)} Cr</span>
          </div>`).join('')}
      </div>
    </details>`;
  }).join('');
}

// ── Rajasthan RDPRWMS Cards ─────────────────────────────────
function renderRajData(rows) {
  const grid = document.getElementById('raj-grid');
  if (!grid) return;
  if (!rows.length) {
    grid.innerHTML = '<p class="loading-placeholder">Rajasthan data unavailable.</p>';
    return;
  }

  const schemes = {};
  rows.forEach(r => {
    const sc = (r['scheme_name'] || 'MLA-LAD').trim();
    if (!schemes[sc]) schemes[sc] = { avail: 0, sanc: 0, years: new Set(), works: 0 };
    schemes[sc].avail += num(r['available_funds_lacs']);
    schemes[sc].sanc += num(r['financial_sanction_lacs']);
    if (r['financial_year']) schemes[sc].years.add(r['financial_year']);
    schemes[sc].works += parseInt(r['no_completed'] || 0, 10) || 0;
  });

  grid.innerHTML = Object.entries(schemes).map(([sc, d]) => `
    <div class="raj-card">
      <div class="raj-scheme">${sc}</div>
      <div class="raj-amount">₹${fmt(d.sanc / 100)} Cr</div>
      <div class="raj-meta">${d.years.size} years | ${d.works.toLocaleString('en-IN')} completed works</div>
    </div>`).join('');
}

// ── Bootstrap ───────────────────────────────────────────────
async function init() {
  applyLanguage(lang);
  setupModal();
  initMap();

  document.getElementById('lang-toggle')?.addEventListener('click', () => {
    applyLanguage(lang === 'en' ? 'hi' : 'en');
  });
  document.getElementById('export-csv-btn')?.addEventListener('click', exportFilteredCSV);
  document.querySelectorAll('.map-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.map-btn').forEach(b => b.classList.remove('is-active'));
      btn.classList.add('is-active');
      activeMapState = btn.getAttribute('data-map-state') || 'ALL';
      updateMap();
    });
  });

  const [fundRows, rajRows] = await Promise.all([
    fetchCSV(DATA_SOURCES.fund),
    fetchCSV(DATA_SOURCES.raj),
  ]);

  if (fundRows.length) {
    allRows = fundRows;
    filtered = [...allRows];
    populateDistricts(allRows);
    renderTable();
    updateRankings();
    renderCharts(allRows);
    renderGraphifyTree(allRows);
  }

  if (rajRows.length) {
    rajData = rajRows;
    renderRajData(rajRows);
  }

  updateMap();

  const normalizedRecords = [
    ...allRows.map(r => ({
      state: 'Uttar Pradesh',
      year: r['Year Label'] || r['Financial Year'] || '',
      house: r['House'] || '',
      district: r['Nodal District'] || '',
      allocated: num(r['Allocated Funds (Lakhs)']),
      sanctioned: num(r['Sanctioned Amount (Lakhs)']),
      spent: num(r['Expenditure (Lakhs)']),
      remaining: num(r['Remaining Balance (Lakhs)']),
    })),
    ...rajData.map(r => ({
      state: 'Rajasthan',
      year: r['financial_year'] || '',
      house: r['scheme_name'] || 'MLA-LAD',
      district: r['district_filter'] || r['constituency'] || '',
      allocated: num(r['available_funds_lacs']),
      sanctioned: num(r['financial_sanction_lacs']),
      spent: num(r['financial_sanction_lacs']),
      remaining: num(r['remaining_amount_lacs']),
    })),
  ];
  mountExplorer(document.getElementById('bi-explorer-root'), normalizedRecords);

  document.getElementById('mla-search')?.addEventListener('input', debounce(applyFilters, 220));
  document.getElementById('district-filter')?.addEventListener('change', applyFilters);
  document.getElementById('year-filter')?.addEventListener('change', applyFilters);
  document.getElementById('house-filter')?.addEventListener('change', applyFilters);
}

function debounce(fn, ms) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

init();
