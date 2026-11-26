import Papa from 'papaparse';
import Chart from 'chart.js/auto';
import L from 'leaflet';
import { TRANSLATIONS } from './i18n.js';
import { normalizeDistrictKey } from './geo.js';
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
let mpLayerGroup = null;
let showMpSeats = false;
let activeMapState = 'ALL';
let geoCache = { states: null, up: null, raj: null, mp: null };
let mynetaData = { UP: [], RAJ: [], LS: [] };
let upVidhanData = [];
let activeProfileScope = 'UP';

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
  const myneta = findMyNetaMatch(rawName);
  const vs = findVidhanMatch(rawName, myneta);

  title.textContent = vs ? `${vs.mla_name_en} (${vs.mla_name_hi})` : cleanName;
  body.innerHTML = `
    <p><strong>District:</strong> ${row['Nodal District'] || vs?.district_en || '—'} | <strong>House:</strong> ${row['House'] || '—'}</p>
    ${vs ? `<div class="graphify-node">
      <strong>UP Vidhan Sabha Official Info:</strong> ${vs.ac_name_en} (${vs.ac_name_hi}) &bull;
      <strong>Party:</strong> ${vs.party_short || vs.party_en} &bull;
      <strong>Gender:</strong> ${vs.gender || '—'} &bull; <strong>DOB:</strong> ${vs.dob || '—'}
      ${vs.phone ? ` &bull; <strong>Phone:</strong> ${vs.phone}` : ''}
      &bull; <a href="${vs.profile_url}" target="_blank" rel="noopener noreferrer" style="color:var(--color-primary);font-weight:600">Vidhan Sabha Profile &rarr;</a>
    </div>` : ''}
    ${myneta ? `<div class="graphify-node" style="margin-bottom:.5rem">
      <strong>MyNeta Affidavit Profile:</strong> ${myneta['Candidate']} (${myneta['Party']}) &bull;
      <strong>Constituency:</strong> ${myneta['Constituency']} &bull;
      <strong>Education:</strong> ${myneta['Education']} &bull;
      <strong>Cases:</strong> ${myneta['Criminal Cases']} &bull;
      <strong>Assets:</strong> ${myneta['Assets Display'] || '—'}
      ${myneta['MyNeta URL'] ? ` &bull; <a href="${myneta['MyNeta URL']}" target="_blank" rel="noopener noreferrer" style="color:var(--color-primary);font-weight:600">View Affidavit &rarr;</a>` : ''}
    </div>` : ''}
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
      <div class="rank-item" data-mla-name="${m.name.replace(/"/g, '&quot;')}">
        <span class="rank-num">${i + 1}</span>
        <div class="rank-info">
          <div class="rank-name">${m.name}</div>
          <div class="rank-sub">${m.dist}</div>
        </div>
        <span class="rank-val ${cls}">${valFn(m)}</span>
      </div>`).join('');
    el.querySelectorAll('.rank-item[data-mla-name]').forEach(item => {
      item.addEventListener('click', () => {
        const nm = item.getAttribute('data-mla-name');
        const row = allRows.find(r => mlaSplit(r['MLA Name & Constituency'] || '') === nm);
        if (row) openMlaModal(row);
      });
    });
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

// ── OpenStreetMap + DataMeet / Indian Shapefiles Choropleth ─
function initMap() {
  const el = document.getElementById('district-map');
  if (!el || leafletMap) return;
  leafletMap = L.map(el).setView([26.9, 77.5], 6);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors | Boundaries: DataMeet / Indian Shapefiles',
    maxZoom: 13,
  }).addTo(leafletMap);
  mapLayerGroup = L.layerGroup().addTo(leafletMap);
  mpLayerGroup = L.layerGroup().addTo(leafletMap);
}

async function fetchGeo(key, url) {
  if (geoCache[key]) return geoCache[key];
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    geoCache[key] = await res.json();
    return geoCache[key];
  } catch {
    return null;
  }
}

async function updateMap() {
  if (!leafletMap || !mapLayerGroup) return;
  mapLayerGroup.clearLayers();

  const agg = {};
  allRows.forEach(r => {
    const raw = (r['Nodal District'] || '').trim();
    const k = normalizeDistrictKey(raw);
    if (!k) return;
    if (!agg[k]) agg[k] = { name: raw, state: 'Uttar Pradesh', alloc: 0, spent: 0 };
    agg[k].alloc += num(r['Allocated Funds (Lakhs)']);
    agg[k].spent += num(r['Expenditure (Lakhs)']);
  });
  rajData.forEach(r => {
    const raw = (r['district_filter'] || '').trim();
    if (!raw || raw.toLowerCase() === 'all') return;
    const k = normalizeDistrictKey(raw);
    if (!k) return;
    if (!agg[k]) agg[k] = { name: raw, state: 'Rajasthan', alloc: 0, spent: 0 };
    agg[k].alloc += num(r['available_funds_lacs']);
    agg[k].spent += num(r['financial_sanction_lacs']);
  });

  const base = import.meta.env.BASE_URL || '/';
  const [statesGeo, upGeo, rajGeo] = await Promise.all([
    fetchGeo('states', `${base}geo/india_states.geojson`),
    activeMapState === 'ALL' || activeMapState === 'UP' ? fetchGeo('up', `${base}geo/up_districts.geojson`) : null,
    activeMapState === 'ALL' || activeMapState === 'RAJ' ? fetchGeo('raj', `${base}geo/raj_districts.geojson`) : null,
  ]);

  if (statesGeo) {
    L.geoJSON(statesGeo, {
      style: { color: '#475569', weight: 1, fillOpacity: 0 },
      interactive: false,
    }).addTo(mapLayerGroup);
  }

  const renderDistrictLayer = (geo, stateLabel) => {
    if (!geo) return;
    L.geoJSON(geo, {
      style: feat => {
        const dt = feat.properties?.dtname || '';
        const rec = agg[normalizeDistrictKey(dt)];
        const pct = rec && rec.alloc > 0 ? Math.min(100, (rec.spent / rec.alloc) * 100) : null;
        const fill = pct === null ? '#94a3b8' : utilColor(pct);
        return { color: '#ffffff', weight: 1, fillColor: fill, fillOpacity: pct === null ? 0.25 : 0.65 };
      },
      onEachFeature: (feat, layer) => {
        const dt = feat.properties?.dtname || 'District';
        const rec = agg[normalizeDistrictKey(dt)];
        const pct = rec && rec.alloc > 0 ? Math.min(100, (rec.spent / rec.alloc) * 100) : null;
        const html = rec
          ? `<strong>${dt}</strong> (${stateLabel})<br/>Allocated: ₹${(rec.alloc / 100).toFixed(1)} Cr<br/>Spent/Sanctioned: ₹${(rec.spent / 100).toFixed(1)} Cr<br/>Utilisation: ${pct.toFixed(1)}%`
          : `<strong>${dt}</strong> (${stateLabel})<br/>No district-level records in filter`;
        layer.bindPopup(html);
        layer.on('mouseover', () => layer.setStyle({ weight: 2, color: '#0f172a', fillOpacity: 0.82 }));
        layer.on('mouseout', () => layer.setStyle({ weight: 1, color: '#ffffff', fillOpacity: pct === null ? 0.25 : 0.65 }));
      },
    }).addTo(mapLayerGroup);
  };

  renderDistrictLayer(upGeo, 'Uttar Pradesh');
  renderDistrictLayer(rajGeo, 'Rajasthan');
}

async function toggleMpLayer() {
  if (!mpLayerGroup) return;
  mpLayerGroup.clearLayers();
  if (!showMpSeats) return;
  const mpGeo = await fetchGeo('mp', 'https://raw.githubusercontent.com/shijithpk/2024_maps_supplement/main/india_ls_seats_543.geojson');
  if (!mpGeo) return;
  L.geoJSON(mpGeo, {
    style: { color: '#1a4fa0', weight: 1.2, fillColor: '#1a4fa0', fillOpacity: 0.08 },
    onEachFeature: (feat, layer) => {
      const p = feat.properties || {};
      const name = p.PC_NAME || p.pc_name || p.name || 'Lok Sabha Seat';
      const st = p.ST_NAME || p.st_name || '';
      layer.bindPopup(`<strong>${name}</strong>${st ? ` (${st})` : ''}<br/>2024 Lok Sabha Constituency`);
    },
  }).addTo(mpLayerGroup);
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
  document.querySelectorAll('.map-btn[data-map-state]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.map-btn[data-map-state]').forEach(b => b.classList.remove('is-active'));
      btn.classList.add('is-active');
      activeMapState = btn.getAttribute('data-map-state') || 'ALL';
      updateMap();
    });
  });
  document.getElementById('toggle-mp-layer')?.addEventListener('click', e => {
    showMpSeats = !showMpSeats;
    e.currentTarget.classList.toggle('is-active', showMpSeats);
    toggleMpLayer();
  });

  const base = import.meta.env.BASE_URL || '/';
  const [fundRows, rajRows, upMyNeta, rajMyNeta, lsMyNeta, upVS] = await Promise.all([
    fetchCSV(DATA_SOURCES.fund),
    fetchCSV(DATA_SOURCES.raj),
    fetchCSV(`${base}data/MyNeta_UP_2022.csv`),
    fetchCSV(`${base}data/MyNeta_Rajasthan_2023.csv`),
    fetchCSV(`${base}data/MyNeta_LokSabha_2024.csv`),
    fetchCSV(`${base}data/UP_VidhanSabha_18_MLAs.csv`),
  ]);
  mynetaData = { UP: upMyNeta, RAJ: rajMyNeta, LS: lsMyNeta };
  upVidhanData = upVS;
  populateProfileDropdown();
  renderProfiles();

  document.querySelectorAll('.profile-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.profile-tab').forEach(b => b.classList.remove('is-active'));
      btn.classList.add('is-active');
      activeProfileScope = btn.getAttribute('data-profile-scope') || 'UP';
      populateProfileDropdown();
      renderProfiles();
    });
  });
  document.getElementById('constituency-dropdown')?.addEventListener('change', e => {
    renderUnifiedCard(e.target.value);
  });
  document.getElementById('profile-search')?.addEventListener('input', debounce(renderProfiles, 200));

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

function populateProfileDropdown() {
  const sel = document.getElementById('constituency-dropdown');
  const card = document.getElementById('unified-neta-card');
  if (!sel) return;
  if (card) card.hidden = true;
  const rows = activeProfileScope === 'UP' && upVidhanData.length
    ? upVidhanData.map(u => ({ key: u.ac_name_en || u.mla_name_en, label: `${u.ac_name_en} — ${u.mla_name_en} (${u.party_short || u.party_en})` }))
    : (mynetaData[activeProfileScope] || []).map(m => ({ key: m['Constituency'], label: `${m['Constituency']} — ${m['Candidate']} (${m['Party']})` }));

  rows.sort((a, b) => a.label.localeCompare(b.label));
  sel.innerHTML = `<option value="">Select Constituency / Neta (${rows.length})...</option>` +
    rows.map(r => `<option value="${r.key.replace(/"/g, '&quot;')}">${r.label}</option>`).join('');
}

function renderUnifiedCard(constKey) {
  const card = document.getElementById('unified-neta-card');
  if (!card) return;
  if (!constKey) { card.hidden = true; return; }

  const norm = s => (s || '').toLowerCase().replace(/\s*\(sc\)|\s*\(st\)/g, '').replace(/[^a-z0-9]/g, '');
  const target = norm(constKey);

  const vs = activeProfileScope === 'UP' ? upVidhanData.find(u => norm(u.ac_name_en) === target) : null;
  const mn = (mynetaData[activeProfileScope] || []).find(m => norm(m['Constituency']) === target);
  const ladRows = activeProfileScope === 'UP'
    ? allRows.filter(r => {
        const txt = (r['MLA Name & Constituency'] || '').toLowerCase();
        return (vs && vs.ac_name_hi && txt.includes(vs.ac_name_hi.toLowerCase()))
          || (vs && vs.mla_name_hi && txt.includes(vs.mla_name_hi.replace(/^श्री\s+|^श्रीमती\s+|^डॉ\.\s+/, '').trim().toLowerCase()));
      })
    : [];

  const totAlloc = ladRows.reduce((s, r) => s + num(r['Allocated Funds (Lakhs)']), 0);
  const totSpent = ladRows.reduce((s, r) => s + num(r['Expenditure (Lakhs)']), 0);
  const pct = totAlloc > 0 ? ((totSpent / totAlloc) * 100).toFixed(1) : '—';

  const titleName = vs ? `${vs.mla_name_en} (${vs.mla_name_hi})` : (mn ? mn['Candidate'] : constKey);
  const subPlace = vs ? `${vs.ac_name_en} (${vs.ac_name_hi}) • ${vs.district_en}` : (mn ? mn['Constituency'] : '');

  card.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.5rem">
      <div>
        <h3 style="font-size:1.1rem;color:var(--color-text)">${titleName}</h3>
        <p style="font-size:.85rem;color:var(--color-text-secondary)">${subPlace}</p>
      </div>
      <span class="house-badge house-badge--vs">${vs ? (vs.party_short || vs.party_en) : (mn ? mn['Party'] : activeProfileScope)}</span>
    </div>
    <div class="unified-grid">
      <div class="unified-col">
        <h4>Official Assembly / House Info</h4>
        ${vs ? `
          <div><strong>Constituency:</strong> ${vs.ac_name_en} / ${vs.ac_name_hi}</div>
          <div><strong>District:</strong> ${vs.district_en} (${vs.district_hi})</div>
          <div><strong>Gender:</strong> ${vs.gender || '—'} | <strong>DOB:</strong> ${vs.dob || '—'}</div>
          <div><strong>Contact:</strong> ${vs.phone || '—'} ${vs.email ? `• ${vs.email}` : ''}</div>
          <div><a href="${vs.profile_url}" target="_blank" rel="noopener noreferrer" style="color:var(--color-primary);font-weight:600">UP Vidhan Sabha Official Profile &rarr;</a></div>
        ` : '<div>Select UP MLAs tab for full Vidhan Sabha profile details.</div>'}
      </div>
      <div class="unified-col">
        <h4>MyNeta Affidavit Summary</h4>
        ${mn ? `
          <div><strong>Party:</strong> ${mn['Party']}</div>
          <div><strong>Criminal Cases:</strong> <strong style="color:${Number(mn['Criminal Cases']) > 0 ? 'var(--color-danger)' : 'var(--color-success)'}">${mn['Criminal Cases']}</strong></div>
          <div><strong>Education:</strong> ${mn['Education'] || '—'}</div>
          <div><strong>Assets:</strong> ${mn['Assets Display'] || '—'}</div>
          <div><strong>Liabilities:</strong> ${mn['Liabilities Display'] || '—'}</div>
          <div><a href="${mn['MyNeta URL']}" target="_blank" rel="noopener noreferrer" style="color:var(--color-primary);font-weight:600">View Full MyNeta Affidavit &rarr;</a></div>
        ` : '<div>No matching MyNeta winner record found.</div>'}
      </div>
      <div class="unified-col">
        <h4>MLA-LAD Fund Performance</h4>
        ${ladRows.length ? `
          <div><strong>Years Tracked:</strong> ${ladRows.length}</div>
          <div><strong>Allocated:</strong> ₹${fmt(totAlloc)} Lakhs</div>
          <div><strong>Spent:</strong> ₹${fmt(totSpent)} Lakhs</div>
          <div><strong>Utilisation:</strong> <strong>${pct}%</strong></div>
        ` : '<div>LAD fund breakdown available for UP MLAs in the main table above.</div>'}
      </div>
    </div>
  `;
  card.hidden = false;
}

function findVidhanMatch(rawName, myneta) {
  if (!upVidhanData.length) return null;
  const norm = s => (s || '').toLowerCase().replace(/\s*\(sc\)|\s*\(st\)/g, '').replace(/[^a-z0-9]/g, '');
  if (myneta && myneta['Constituency']) {
    const c = norm(myneta['Constituency']);
    const hit = upVidhanData.find(u => norm(u.ac_name_en) === c);
    if (hit) return hit;
  }
  const clean = (rawName || '').toLowerCase();
  return upVidhanData.find(u => {
    const ac = (u.ac_name_hi || '').trim().toLowerCase();
    const nm = (u.mla_name_hi || '').replace(/^श्री\s+|^श्रीमती\s+|^डॉ\.\s+/, '').trim().toLowerCase();
    return (ac && clean.includes(ac)) || (nm && clean.includes(nm));
  }) || null;
}

function openProfileModal(constKey, scope) {
  const modal = document.getElementById('mla-modal');
  const title = document.getElementById('modal-title');
  const body = document.getElementById('modal-body');
  if (!modal || !title || !body) return;

  const norm = s => (s || '').toLowerCase().replace(/\s*\(sc\)|\s*\(st\)/g, '').replace(/[^a-z0-9]/g, '');
  const target = norm(constKey);
  const vs = scope === 'UP' ? upVidhanData.find(u => norm(u.ac_name_en) === target) : null;
  const mn = (mynetaData[scope] || []).find(m => norm(m['Constituency']) === target);
  const ladRows = scope === 'UP'
    ? allRows.filter(r => {
        const txt = (r['MLA Name & Constituency'] || '').toLowerCase();
        return (vs && vs.ac_name_hi && txt.includes(vs.ac_name_hi.toLowerCase()))
          || (vs && vs.mla_name_hi && txt.includes(vs.mla_name_hi.replace(/^श्री\s+|^श्रीमती\s+|^डॉ\.\s+/, '').trim().toLowerCase()));
      })
    : [];

  title.textContent = vs ? `${vs.mla_name_en} (${vs.mla_name_hi})` : (mn ? mn['Candidate'] : constKey);
  body.innerHTML = `
    ${vs ? `<div class="graphify-node">
      <strong>UP Vidhan Sabha Official Bio:</strong> ${vs.ac_name_en} (${vs.ac_name_hi}) &bull; <strong>District:</strong> ${vs.district_en} &bull;
      <strong>Party:</strong> ${vs.party_short || vs.party_en} &bull; <strong>Gender:</strong> ${vs.gender || '—'} &bull; <strong>DOB:</strong> ${vs.dob || '—'}
      ${vs.phone ? ` &bull; <strong>Phone:</strong> ${vs.phone}` : ''}
      &bull; <a href="${vs.profile_url}" target="_blank" rel="noopener noreferrer" style="color:var(--color-primary);font-weight:600">Vidhan Sabha Profile &rarr;</a>
    </div>` : ''}
    ${mn ? `<div class="graphify-node">
      <strong>MyNeta Affidavit:</strong> ${mn['Candidate']} (${mn['Party']}) &bull; <strong>Education:</strong> ${mn['Education']} &bull;
      <strong>Cases:</strong> ${mn['Criminal Cases']} &bull; <strong>Assets:</strong> ${mn['Assets Display'] || '—'} &bull; <strong>Liabilities:</strong> ${mn['Liabilities Display'] || '—'}
      ${mn['MyNeta URL'] ? ` &bull; <a href="${mn['MyNeta URL']}" target="_blank" rel="noopener noreferrer" style="color:var(--color-primary);font-weight:600">Full Affidavit &rarr;</a>` : ''}
    </div>` : ''}
    ${ladRows.length ? `<div class="table-wrap"><table class="data-table"><thead><tr><th>Year</th><th class="num">Allocated (L)</th><th class="num">Spent (L)</th><th class="num">Remaining (L)</th></tr></thead><tbody>
      ${ladRows.map(h => `<tr><td>${h['Year Label'] || h['Financial Year'] || ''}</td><td class="num">₹${fmt(h['Allocated Funds (Lakhs)'])}</td><td class="num">₹${fmt(h['Expenditure (Lakhs)'])}</td><td class="num">₹${fmt(h['Remaining Balance (Lakhs)'])}</td></tr>`).join('')}
    </tbody></table></div>` : ''}
  `;
  modal.hidden = false;
}

function findMyNetaMatch(rawName) {
  const list = mynetaData.UP || [];
  if (!list.length || !rawName) return null;
  const clean = rawName.toLowerCase();
  return list.find(m => {
    const c = (m['Constituency'] || '').toLowerCase().replace(/\s*\(sc\)|\s*\(st\)/g, '').trim();
    return c && clean.includes(c);
  }) || null;
}

function renderProfiles() {
  const tbody = document.getElementById('profiles-tbody');
  const meta = document.getElementById('profiles-meta');
  if (!tbody) return;
  const q = (document.getElementById('profile-search')?.value || '').toLowerCase();
  const rows = (mynetaData[activeProfileScope] || []).filter(r => {
    if (!q) return true;
    return (r['Candidate'] || '').toLowerCase().includes(q)
      || (r['Constituency'] || '').toLowerCase().includes(q)
      || (r['Party'] || '').toLowerCase().includes(q);
  });

  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="8" class="loading-row">No matching profiles found.</td></tr>';
    if (meta) meta.textContent = '';
    return;
  }

  const norm = s => (s || '').toLowerCase().replace(/\s*\(sc\)|\s*\(st\)/g, '').replace(/[^a-z0-9]/g, '');
  const slice = rows.slice(0, 120);
  tbody.innerHTML = slice.map(r => {
    const cases = parseInt(r['Criminal Cases'] || 0, 10) || 0;
    const caseColor = cases > 0 ? 'var(--color-danger)' : 'var(--color-success)';
    const vs = activeProfileScope === 'UP' ? upVidhanData.find(u => norm(u.ac_name_en) === norm(r['Constituency'])) : null;
    const constAttr = (r['Constituency'] || '').replace(/"/g, '&quot;');
    return `<tr data-const="${constAttr}" data-scope="${activeProfileScope}">
      <td>
        <div class="mla-name">${r['Candidate'] || ''}</div>
        ${vs ? `<div class="mla-area">${vs.mla_name_hi} &bull; ${vs.district_en}</div>` : ''}
      </td>
      <td>${r['Constituency'] || ''}</td>
      <td>${r['Party'] || ''}</td>
      <td class="num" style="color:${caseColor};font-weight:700">${cases}</td>
      <td>${r['Education'] || '—'}</td>
      <td class="num">${r['Assets Display'] || '—'}</td>
      <td class="num">${r['Liabilities Display'] || '—'}</td>
      <td>
        ${r['MyNeta URL'] ? `<a href="${r['MyNeta URL']}" target="_blank" rel="noopener noreferrer" onclick="event.stopPropagation()" style="color:var(--color-primary);font-weight:600">Affidavit &rarr;</a>` : '—'}
        ${vs ? `<br/><a href="${vs.profile_url}" target="_blank" rel="noopener noreferrer" onclick="event.stopPropagation()" style="color:var(--color-accent);font-weight:600;font-size:.76rem">Vidhan Sabha &rarr;</a>` : ''}
      </td>
    </tr>`;
  }).join('');

  tbody.querySelectorAll('tr[data-const]').forEach(tr => {
    tr.addEventListener('click', () => {
      openProfileModal(tr.getAttribute('data-const'), tr.getAttribute('data-scope'));
    });
  });

  if (meta) meta.textContent = `Showing ${slice.length} of ${rows.length} profiles (${activeProfileScope}) — click any row for full wholesome profile`;
}

function debounce(fn, ms) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

init();
