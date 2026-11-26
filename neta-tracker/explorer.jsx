import React, { useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';

const DIMENSIONS = [
  { key: 'year', label: 'Financial Year' },
  { key: 'state', label: 'State' },
  { key: 'house', label: 'House / Scheme' },
  { key: 'district', label: 'District' },
];

const METRICS = [
  { key: 'allocated', label: 'Allocated (Lakhs)' },
  { key: 'sanctioned', label: 'Sanctioned (Lakhs)' },
  { key: 'spent', label: 'Expenditure (Lakhs)' },
  { key: 'remaining', label: 'Remaining (Lakhs)' },
];

function BIExplorer({ records }) {
  const [stateFilter, setStateFilter] = useState('ALL');
  const [dim, setDim] = useState('year');
  const [metric, setMetric] = useState('spent');
  const [agg, setAgg] = useState('sum');
  const [chartType, setChartType] = useState('bar');
  const [limit, setLimit] = useState(12);

  const scoped = useMemo(() => {
    if (stateFilter === 'ALL') return records;
    return records.filter(r => r.state === stateFilter);
  }, [records, stateFilter]);

  const grouped = useMemo(() => {
    const map = new Map();
    for (const r of scoped) {
      const k = (r[dim] || 'Unspecified').trim();
      if (!map.has(k)) map.set(k, { key: k, sum: 0, count: 0 });
      const entry = map.get(k);
      entry.sum += Number(r[metric] || 0);
      entry.count += 1;
    }
    const rows = Array.from(map.values()).map(d => ({
      key: d.key,
      value: agg === 'avg' ? (d.count ? d.sum / d.count : 0) : agg === 'count' ? d.count : d.sum,
      count: d.count,
    }));
    rows.sort((a, b) => b.value - a.value);
    return rows.slice(0, limit);
  }, [scoped, dim, metric, agg, limit]);

  const maxVal = useMemo(() => Math.max(1, ...grouped.map(g => g.value)), [grouped]);
  const totalVal = useMemo(() => grouped.reduce((s, g) => s + g.value, 0) || 1, [grouped]);

  const colors = ['#1a4fa0', '#e8650a', '#059669', '#2563eb', '#d97706', '#0f766e', '#be123c', '#4338ca', '#0284c7', '#65a30d', '#b45309', '#475569'];

  return (
    <div className="bi-studio">
      <div className="bi-toolbar">
        <label className="bi-field">
          <span>Dataset</span>
          <select value={stateFilter} onChange={e => setStateFilter(e.target.value)}>
            <option value="ALL">UP + Rajasthan ({records.length.toLocaleString()})</option>
            <option value="Uttar Pradesh">Uttar Pradesh</option>
            <option value="Rajasthan">Rajasthan</option>
          </select>
        </label>
        <label className="bi-field">
          <span>Group By (X)</span>
          <select value={dim} onChange={e => setDim(e.target.value)}>
            {DIMENSIONS.map(d => <option key={d.key} value={d.key}>{d.label}</option>)}
          </select>
        </label>
        <label className="bi-field">
          <span>Measure (Y)</span>
          <select value={metric} onChange={e => setMetric(e.target.value)}>
            {METRICS.map(m => <option key={m.key} value={m.key}>{m.label}</option>)}
          </select>
        </label>
        <label className="bi-field">
          <span>Aggregation</span>
          <select value={agg} onChange={e => setAgg(e.target.value)}>
            <option value="sum">Sum</option>
            <option value="avg">Average</option>
            <option value="count">Record Count</option>
          </select>
        </label>
        <label className="bi-field">
          <span>View</span>
          <select value={chartType} onChange={e => setChartType(e.target.value)}>
            <option value="bar">Horizontal Bar</option>
            <option value="pie">Donut Share</option>
            <option value="table">Pivot Table</option>
          </select>
        </label>
        <label className="bi-field">
          <span>Top N</span>
          <select value={limit} onChange={e => setLimit(Number(e.target.value))}>
            <option value={8}>8</option>
            <option value={12}>12</option>
            <option value={25}>25</option>
          </select>
        </label>
      </div>

      <div className="bi-canvas">
        {!grouped.length && <p className="bi-empty">Loading dataset into BI Studio...</p>}

        {grouped.length > 0 && chartType === 'bar' && (
          <div className="bi-bars">
            {grouped.map((g, i) => {
              const pct = (g.value / maxVal) * 100;
              return (
                <div className="bi-bar-row" key={g.key}>
                  <div className="bi-bar-label" title={g.key}>{g.key}</div>
                  <div className="bi-bar-track">
                    <div
                      className="bi-bar-fill"
                      style={{ transform: `scaleX(${Math.max(0.01, pct / 100)})`, backgroundColor: colors[i % colors.length] }}
                    />
                  </div>
                  <div className="bi-bar-val">
                    {agg === 'count' ? g.value.toLocaleString('en-IN') : `₹${(g.value / 100).toFixed(1)} Cr`}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {grouped.length > 0 && chartType === 'pie' && (
          <div className="bi-pie-wrap">
            <svg viewBox="0 0 220 220" className="bi-pie-svg" aria-label="Interactive share chart">
              {(() => {
                let acc = 0;
                const r = 80;
                const cx = 110;
                const cy = 110;
                const circ = 2 * Math.PI * r;
                return grouped.map((g, i) => {
                  const frac = g.value / totalVal;
                  const dash = frac * circ;
                  const offset = -acc * circ;
                  acc += frac;
                  return (
                    <circle
                      key={g.key}
                      cx={cx}
                      cy={cy}
                      r={r}
                      fill="none"
                      stroke={colors[i % colors.length]}
                      strokeWidth="34"
                      strokeDasharray={`${dash} ${circ}`}
                      strokeDashoffset={offset}
                      transform={`rotate(-90 ${cx} ${cy})`}
                    />
                  );
                });
              })()}
              <text x="110" y="106" textAnchor="middle" className="bi-pie-center-num">
                {agg === 'count' ? totalVal.toLocaleString('en-IN') : `₹${(totalVal / 100).toFixed(0)}Cr`}
              </text>
              <text x="110" y="124" textAnchor="middle" className="bi-pie-center-sub">Total</text>
            </svg>
            <div className="bi-legend">
              {grouped.map((g, i) => (
                <div className="bi-legend-item" key={g.key}>
                  <span className="bi-legend-swatch" style={{ backgroundColor: colors[i % colors.length] }} />
                  <span className="bi-legend-name">{g.key}</span>
                  <span className="bi-legend-pct">{((g.value / totalVal) * 100).toFixed(1)}%</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {grouped.length > 0 && chartType === 'table' && (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>{DIMENSIONS.find(d => d.key === dim)?.label}</th>
                  <th className="num">Records</th>
                  <th className="num">{agg === 'count' ? 'Count' : `${METRICS.find(m => m.key === metric)?.label}`}</th>
                  <th className="num">Share</th>
                </tr>
              </thead>
              <tbody>
                {grouped.map(g => (
                  <tr key={g.key}>
                    <td>{g.key}</td>
                    <td className="num">{g.count.toLocaleString('en-IN')}</td>
                    <td className="num">{agg === 'count' ? g.value.toLocaleString('en-IN') : g.value.toLocaleString('en-IN', { maximumFractionDigits: 2 })}</td>
                    <td className="num">{((g.value / totalVal) * 100).toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

let rootInstance = null;
export function mountExplorer(container, records) {
  if (!container) return;
  if (!rootInstance) rootInstance = createRoot(container);
  rootInstance.render(<BIExplorer records={records} />);
}
