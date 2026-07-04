import React from "react";
import { statusColor } from "./theme.js";

export const fmtNum = (n) => (n == null ? "–" : Math.round(n).toLocaleString("sk-SK").replace(/,/g, " "));
export const fmtDur = (min) => {
  if (min == null) return "–";
  const h = Math.floor(min / 60), m = Math.round(min % 60);
  return `${h}:${String(m).padStart(2, "0")}`;
};

export function formatKpi(key, v) {
  if (v == null) return "–";
  if (key === "sleep_minutes") return fmtDur(v);
  if (key === "steps") return fmtNum(v);
  if (key === "load") return Math.round(v);
  return Math.round(v);
}

export function KpiTile({ kpi, p }) {
  const { key, label, unit, value, delta, better, spark } = kpi;
  let cls = "flat", arrow = "→", dtxt = delta == null ? "" : Math.abs(delta).toFixed(key === "load" ? 0 : 0);
  if (delta != null && Math.abs(delta) > 0.5) {
    const goodDir = better === "lower" ? delta < 0 : delta > 0;
    if (better === "neutral") { cls = "flat"; arrow = delta > 0 ? "▲" : "▼"; }
    else { cls = goodDir ? "up" : "down"; arrow = delta > 0 ? "▲" : "▼"; }
  }
  const suffix = key === "sleep_minutes" ? " h" : unit ? ` ${unit}` : "";
  return (
    <div className="kpi">
      <div className="k-top">
        <span className="k-label">{label}</span>
        {delta != null && <span className={`k-delta ${cls}`}>{arrow} {dtxt}{key === "sleep_minutes" ? " min" : ""}</span>}
      </div>
      <div className="k-val">{formatKpi(key, value)}{suffix && <small>{suffix}</small>}</div>
      <Sparkline data={spark} color={p.blue} />
    </div>
  );
}

export function Sparkline({ data, color }) {
  if (!data || data.length < 2) return <svg width="100%" height="30" />;
  const W = 220, H = 30, lo = Math.min(...data), hi = Math.max(...data) || 1;
  const X = (i) => 3 + (W - 6) * i / (data.length - 1);
  const Y = (v) => 3 + (H - 6) * (1 - (v - lo) / ((hi - lo) || 1));
  const d = data.map((v, i) => `${i ? "L" : "M"} ${X(i).toFixed(1)} ${Y(v).toFixed(1)}`).join(" ");
  return (
    <svg width="100%" height="30" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ marginTop: 8, display: "block" }}>
      <path d={d} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" opacity="0.85" />
    </svg>
  );
}

export function ReadinessRing({ score, p }) {
  const R = 56, C = 2 * Math.PI * R;
  const s = score == null ? 0 : score;
  const col = statusColor(p, score);
  return (
    <div className="ring-wrap">
      <svg width="132" height="132" viewBox="0 0 132 132">
        <circle cx="66" cy="66" r={R} fill="none" stroke="var(--card2)" strokeWidth="12" />
        <circle cx="66" cy="66" r={R} fill="none" stroke={col} strokeWidth="12" strokeLinecap="round"
          strokeDasharray={C.toFixed(1)} strokeDashoffset={(C * (1 - s / 100)).toFixed(1)}
          transform="rotate(-90 66 66)" />
      </svg>
      <div className="ring-num"><div><b>{score == null ? "–" : Math.round(score)}</b><span>/ 100</span></div></div>
    </div>
  );
}

const COMP_LABELS = { rhr_score: "Pokojový HR", sleep_score_c: "Spánok", stress_score: "Stres", acwr_score: "Záťaž (ACWR)" };
const COMP_KEYS = ["rhr_score", "sleep_score_c", "stress_score", "acwr_score"];

export function ComponentBars({ components, p }) {
  const colors = { rhr_score: p.blue, sleep_score_c: p.aqua, stress_score: p.yellow, acwr_score: p.violet };
  const score = components.readiness;
  const col = statusColor(p, score);
  return (
    <div className="comp">
      <div style={{ marginBottom: 2 }}>
        <span className="status-pill" style={{ background: `${col}26`, color: col }}>
          <span className="dot" style={{ background: col }} />{statusLabel(score)}
        </span>
      </div>
      {COMP_KEYS.filter((k) => components[k] != null).map((k) => (
        <div className="row" key={k}>
          <span className="lbl">{COMP_LABELS[k]}</span>
          <span className="bar"><i style={{ width: `${Math.min(100, components[k])}%`, background: colors[k] }} /></span>
          <span className="val">{Math.round(components[k])}</span>
        </div>
      ))}
    </div>
  );
}

export function statusLabel(score) {
  if (score == null) return "–";
  if (score >= 75) return "Výborné zotavenie";
  if (score >= 55) return "Dobré zotavenie";
  if (score >= 40) return "Priemerné";
  return "Nízke — oddýchni si";
}
