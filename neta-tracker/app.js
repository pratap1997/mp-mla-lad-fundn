// Neta Tracker — app.js
// Loads CSV data from GitHub raw URLs, renders interactive MLA fund table + charts

const GITHUB_RAW = 'https://raw.githubusercontent.com/pratap1997/mp-mla-lad-fundn/main';

const DATA_SOURCES = {
  fund:    `${GITHUB_RAW}/UP_MLA_LAD_Fund_YearWise.csv`,
  summary: `${GITHUB_RAW}/MLA_LADS_UP_Summary.csv`,
  raj:     `${GITHUB_RAW}/Rajasthan_RDPRWMS/MLA_LAD_Rajasthan_YearWise.csv`,
};

// ── State ──────────────────────────────────────────────────
let allRows    = [];
let filtered   = [];
let rajData    = [];
let sortCol    = null;
let sortDir    = 1;
const PAGE_SIZE = 50;
let page       = 1;

// ── Utils ──────────────────────────────────────────────────
function parseCSV(text) {
  const lines = text.trim().split('\n');
  const headers = lines[0].split(',').map(h => h.replace(/^"|"$/g, '').trim());
  return lines.slice(1).map(line => {
    const cols = [];
    let inQ = false, cur = '';
    for (const ch of line) {
      if (ch === '"') { inQ = !inQ; continue; }
      if (ch === ',' && !inQ) { cols.push(cur); cur = ''; continue; }
      cur += ch;
    }
    cols.push(cur);
    const obj = {};
    headers.forEach((h, i) => obj[h] = (cols[i] || '').trim());
    return obj;
  }).filter(r => Object.values(r).some(v => v));
}

async function fetchCSV(url) {
  try {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return parseCSV(await r.text());
  } catch (e) {
    console.warn('Failed to fetch', url, e);
    return [];
  }
}

function fmt(v, suffix = '') {
  const n = parseFloat(v);
  if (isNaN(n)) return '—';
  return n.toLocaleString('en-IN', { maximumFractionDigits: 2 }) + suffix;
}

function utilColor(pct) {
  if (pct >= 80) return '#059669';
  if (pct >= 50) return '#d97706';
  return '#dc2626';
}

function mlaSplit(raw) {
  // "1 श्री X — Constituency" or just the name
  const m = raw?.match(/^\d+\s+(.+)$/);
  return m ? m[1] : (raw || '');
}

// ── Render Table ───────────────────────────────────────────
function renderTable() {
  const tbody = document.getElementById('mla-tbody');
  const meta  = document.getElementById('table-meta');
  if (!filtered.length) {
    tbody.innerHTML = `<tr><td colspan="9" style="text-align:center;padding:3rem;color:#94a3b8">No results found. Try a different search.</td></tr>`;
    meta.textContent = '';
    return;
  }

  const start = (page - 1) * PAGE_SIZE;
  const slice = filtered.slice(start, start + PAGE_SIZE);

  tbody.innerHTML = slice.map(row => {
    const alloc  = parseFloat(row['Allocated Funds (Lakhs)'] || row['Allocated'] || 0);
    const spent  = parseFloat(row['Expenditure (Lakhs)'] || row['Expenditure'] || 0);
    const sanc   = parseFloat(row['Sanctioned Amount (Lakhs)'] || row['Sanctioned'] || 0);
    const rem    = parseFloat(row['Remaining Balance (Lakhs)'] || row['Remaining'] || 0);
    const pct    = alloc > 0 ? Math.min(100, (spent / alloc) * 100) : 0;
    const color  = utilColor(pct);
    const house  = row['House'] || '';
    const isVS   = house.includes('Sabha');
    const year   = row['Year Label'] || row['Financial Year'] || '';
    const mlaRaw = row['MLA Name & Constituency'] || '';
    const name   = mlaSplit(mlaRaw);
    const dist   = row['Nodal District'] || '';

    return `<tr>
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

  meta.textContent = `Showing ${start + 1}–${Math.min(start + PAGE_SIZE, filtered.length)} of ${filtered.length.toLocaleString()} rows`;
  renderPagination();
}

function renderPagination() {
  const existing = document.getElementById('pagination');
  if (existing) existing.remove();
  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  if (totalPages <= 1) return;

  const wrap = document.createElement('div');
  wrap.id = 'pagination';
  wrap.style.cssText = 'display:flex;gap:.5rem;justify-content:center;margin-top:1.25rem;flex-wrap:wrap;';

  const addBtn = (label, pg, disabled) => {
    const btn = document.createElement('button');
    btn.textContent = label;
    btn.disabled = disabled;
    btn.style.cssText = `padding:.4rem .85rem;border:1.5px solid ${pg === page ? '#1a4fa0' : '#e2e8f0'};
      background:${pg === page ? '#1a4fa0' : '#fff'};color:${pg === page ? '#fff' : '#0f172a'};
      border-radius:8px;font-size:.82rem;font-weight:600;cursor:${disabled?'default':'pointer'};
      opacity:${disabled?.4:1};font-family:inherit;`;
    btn.addEventListener('click', () => { page = pg; renderTable(); window.scrollTo({top: document.getElementById('mla-data').offsetTop - 80, behavior: 'smooth'}); });
    wrap.appendChild(btn);
  };

  addBtn('‹ Prev', page - 1, page === 1);
  const startP = Math.max(1, page - 2);
  const endP   = Math.min(totalPages, startP + 4);
  for (let p = startP; p <= endP; p++) addBtn(p, p, false);
  addBtn('Next ›', page + 1, page === totalPages);

  document.getElementById('table-meta').after(wrap);
}

// ── Filter & Search ────────────────────────────────────────
function applyFilters() {
  const q     = document.getElementById('mla-search').value.toLowerCase();
  const year  = document.getElementById('year-filter').value;
  const house = document.getElementById('house-filter').value;

  filtered = allRows.filter(row => {
    const mlaName = (row['MLA Name & Constituency'] || '').toLowerCase();
    const dist    = (row['Nodal District'] || '').toLowerCase();
    const rowYear = row['Year Label'] || row['Financial Year'] || '';
    const rowHouse= row['House'] || '';

    if (q && !mlaName.includes(q) && !dist.includes(q)) return false;
    if (year && !rowYear.includes(year)) return false;
    if (house && !rowHouse.includes(house.split(' ')[0])) return false;
    return true;
  });

  page = 1;
  renderTable();
  updateRankings();
}

// ── Rankings ───────────────────────────────────────────────
function updateRankings() {
  const byMLA = {};
  filtered.forEach(row => {
    const name = mlaSplit(row['MLA Name & Constituency'] || '');
    if (!name) return;
    if (!byMLA[name]) byMLA[name] = { name, dist: row['Nodal District'] || '', spent: 0, alloc: 0 };
    byMLA[name].spent += parseFloat(row['Expenditure (Lakhs)'] || 0);
    byMLA[name].alloc += parseFloat(row['Allocated Funds (Lakhs)'] || row['Allocated'] || 0);
  });

  const arr = Object.values(byMLA).filter(m => m.alloc > 0);
  arr.forEach(m => m.pct = m.alloc > 0 ? (m.spent / m.alloc) * 100 : 0);

  const topSpenders = [...arr].sort((a, b) => b.spent - a.spent).slice(0, 10);
  const lowUtil     = [...arr].sort((a, b) => a.pct - b.pct).slice(0, 10);

  const renderList = (el, items, valFn, colorClass) => {
    el.innerHTML = items.map((m, i) => `
      <div class="rank-item">
        <span class="rank-num">${i + 1}</span>
        <div class="rank-info">
          <div class="rank-name">${m.name}</div>
          <div class="rank-sub">${m.dist}</div>
        </div>
        <span class="rank-val ${colorClass}">${valFn(m)}</span>
      </div>
    `).join('');
  };

  renderList(document.getElementById('top-spenders'), topSpenders,
    m => `₹${fmt(m.spent)}L`, 'rank-val--green');
  renderList(document.getElementById('low-spenders'), lowUtil,
    m => `${m.pct.toFixed(1)}%`, 'rank-val--red');
}

// ── Chart ──────────────────────────────────────────────────
function drawChart(rows) {
  const canvas = document.getElementById('year-chart');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  const years = ['2023-24', '2024-25', '2025-26', '2026-27'];
  const alloc  = [], spent = [], sanc = [];

  years.forEach(yr => {
    const subset = rows.filter(r => (r['Year Label'] || '').includes(yr) && r['House']?.includes('Sabha'));
    alloc.push(subset.reduce((s, r) => s + parseFloat(r['Allocated Funds (Lakhs)'] || 0), 0) / 100);
    spent.push(subset.reduce((s, r) => s + parseFloat(r['Expenditure (Lakhs)'] || 0), 0) / 100);
    sanc.push(subset.reduce((s, r) => s + parseFloat(r['Sanctioned Amount (Lakhs)'] || 0), 0) / 100);
  });

  const W = canvas.parentElement.clientWidth - 48;
  const H = 300;
  canvas.width = W;
  canvas.height = H;

  const pad = { top: 30, right: 30, bottom: 50, left: 70 };
  const iW = W - pad.left - pad.right;
  const iH = H - pad.top - pad.bottom;
  const maxV = Math.max(...alloc, ...spent, ...sanc);

  ctx.clearRect(0, 0, W, H);

  // Grid lines
  ctx.strokeStyle = '#e2e8f0'; ctx.lineWidth = 1;
  for (let i = 0; i <= 5; i++) {
    const y = pad.top + (iH / 5) * i;
    ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(pad.left + iW, y); ctx.stroke();
    ctx.fillStyle = '#94a3b8'; ctx.font = '11px Inter, sans-serif';
    ctx.fillText(`₹${((maxV * (1 - i / 5)) / 100).toFixed(0)}Cr`, 4, y + 4);
  }

  // Bars
  const barW = iW / years.length;
  const groups = [
    { data: alloc, color: '#2563eb', label: 'Allocated' },
    { data: spent, color: '#059669', label: 'Spent' },
    { data: sanc,  color: '#f59e0b', label: 'Sanctioned' },
  ];
  const bW = (barW * .6) / groups.length;

  years.forEach((yr, yi) => {
    const baseX = pad.left + yi * barW + barW * .2;
    groups.forEach((g, gi) => {
      const val = g.data[yi];
      const bH  = (val / maxV) * iH;
      const x   = baseX + gi * (bW + 2);
      const y   = pad.top + iH - bH;
      ctx.fillStyle = g.color;
      ctx.beginPath();
      ctx.roundRect?.(x, y, bW, bH, [3, 3, 0, 0]) ?? ctx.rect(x, y, bW, bH);
      ctx.fill();
    });
    // X label
    ctx.fillStyle = '#475569'; ctx.font = '11px Inter';
    ctx.textAlign = 'center';
    ctx.fillText(yr, pad.left + yi * barW + barW / 2, H - 15);
  });

  // Legend
  let lx = pad.left;
  groups.forEach(g => {
    ctx.fillStyle = g.color;
    ctx.fillRect(lx, 8, 12, 12);
    ctx.fillStyle = '#475569'; ctx.font = '11px Inter'; ctx.textAlign = 'left';
    ctx.fillText(g.label, lx + 16, 19);
    lx += 90;
  });
}

// ── Rajasthan cards ────────────────────────────────────────
function renderRajData(rows) {
  const grid = document.getElementById('raj-grid');
  if (!rows.length) {
    grid.innerHTML = '<p style="color:#94a3b8;font-size:.88rem">Rajasthan data could not be loaded. <a href="https://github.com/pratap1997/mp-mla-lad-fundn/tree/main/Rajasthan_RDPRWMS" style="color:#1a4fa0">View on GitHub →</a></p>';
    return;
  }

  // Group by scheme
  const schemes = {};
  rows.forEach(r => {
    const sc = r['Scheme'] || r['scheme'] || r['Category'] || 'Unknown';
    if (!schemes[sc]) schemes[sc] = { total: 0, years: new Set(), works: 0 };
    schemes[sc].total += parseFloat(r['Amount'] || r['Total Amount'] || r['amount'] || 0);
    schemes[sc].years.add(r['Year'] || r['year'] || '');
    schemes[sc].works += parseInt(r['Works'] || r['works'] || r['count'] || 0);
  });

  grid.innerHTML = Object.entries(schemes).slice(0, 20).map(([sc, d]) => `
    <div class="raj-card">
      <div class="raj-scheme">${sc}</div>
      <div class="raj-amount">₹${fmt(d.total / 100)}Cr</div>
      <div class="raj-meta">${d.years.size} years · ${d.works.toLocaleString()} works</div>
    </div>
  `).join('');
}

// ── Bootstrap ──────────────────────────────────────────────
async function init() {
  const [fundRows, rajRows] = await Promise.all([
    fetchCSV(DATA_SOURCES.fund),
    fetchCSV(DATA_SOURCES.raj),
  ]);

  if (fundRows.length) {
    allRows  = fundRows;
    filtered = [...allRows];
    renderTable();
    updateRankings();
    drawChart(allRows);
  } else {
    // Fallback: show static demo message
    document.getElementById('mla-tbody').innerHTML = `
      <tr><td colspan="9" style="text-align:center;padding:2rem;color:#94a3b8">
        Data is loading from GitHub. If this persists, 
        <a href="https://github.com/pratap1997/mp-mla-lad-fundn" style="color:#1a4fa0">download CSV directly</a>.
      </td></tr>`;
  }

  if (rajRows.length) {
    rajData = rajRows;
    renderRajData(rajRows);
  }

  // Listeners
  document.getElementById('mla-search').addEventListener('input', debounce(applyFilters, 250));
  document.getElementById('year-filter').addEventListener('change', applyFilters);
  document.getElementById('house-filter').addEventListener('change', applyFilters);

  // Animated number tickers in hero
  animateTicker('stat-mlas',   0, 512,     800);
  animateTicker('stat-works',  0, 145195, 1200, true);
}

function debounce(fn, ms) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

function animateTicker(id, from, to, duration, comma = false) {
  const el = document.getElementById(id);
  if (!el) return;
  const start = performance.now();
  const tick = now => {
    const p = Math.min((now - start) / duration, 1);
    const ease = 1 - Math.pow(1 - p, 3);
    const val = Math.round(from + (to - from) * ease);
    el.textContent = comma ? val.toLocaleString('en-IN') : val.toLocaleString();
    if (p < 1) requestAnimationFrame(tick);
  };
  setTimeout(() => requestAnimationFrame(tick), 300);
}

// Redraw chart on resize
window.addEventListener('resize', debounce(() => drawChart(allRows), 200));

init();
