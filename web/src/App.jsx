import React, { useEffect, useState } from "react";
import { api } from "./api.js";
import { PALETTES, applyTheme } from "./theme.js";
import { KpiTile, ReadinessRing, ComponentBars, fmtDur, fmtNum } from "./ui.jsx";
import {
  ReadinessTrend, RhrVsBaseline, SleepStages, TrainingLoad, AcwrChart,
  WeightTrend, SleepScatter, CorrHeatmap,
} from "./charts.jsx";

const RANGES = ["7d", "30d", "90d", "all"];
const TABS = [["overview", "Prehľad"], ["workouts", "Tréningy"], ["insights", "Insights"], ["goals", "Ciele"]];

export default function App() {
  const [theme, setTheme] = useState(localStorage.getItem("theme") || "dark");
  const [range, setRange] = useState("30d");
  const [tab, setTab] = useState("overview");
  const [summary, setSummary] = useState(null);
  const [ts, setTs] = useState(null);
  const [workouts, setWorkouts] = useState(null);
  const [corr, setCorr] = useState(null);
  const [goals, setGoals] = useState(null);
  const [err, setErr] = useState(null);
  const p = PALETTES[theme];

  useEffect(() => { applyTheme(theme); localStorage.setItem("theme", theme); }, [theme]);

  useEffect(() => {
    setErr(null);
    api.summary(range).then(setSummary).catch((e) => setErr(String(e)));
    api.timeseries(range).then(setTs).catch((e) => setErr(String(e)));
  }, [range]);

  useEffect(() => {
    if (tab === "workouts" && !workouts) api.workouts("90d").then(setWorkouts).catch(() => {});
    if (tab === "insights" && !corr) api.correlations("90d").then(setCorr).catch(() => {});
    if (tab === "goals" && !goals) api.goals().then(setGoals).catch(() => {});
  }, [tab]);

  const days = ts?.days || [];

  return (
    <div className="wrap">
      <header className="top">
        <div className="brand">
          <div className="logo">◈</div>
          <div>
            <h1>shealth <span className="muted" style={{ fontWeight: 500 }}>· Galaxy Watch Ultra</span></h1>
            <div className="sub">{summary?.as_of ? `k dátumu ${summary.as_of}` : "načítavam…"}</div>
          </div>
        </div>
        <div className="controls">
          <div className="ranges">
            {RANGES.map((r) => (
              <button key={r} className={r === range ? "active" : ""} onClick={() => setRange(r)}>
                {r === "all" ? "Vše" : r}
              </button>
            ))}
          </div>
          <button className="icon-btn" title="Prepnúť tému" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
            {theme === "dark" ? "☀" : "☾"}
          </button>
        </div>
      </header>

      <div className="tabs">
        {TABS.map(([id, label]) => (
          <button key={id} className={id === tab ? "active" : ""} onClick={() => setTab(id)}>{label}</button>
        ))}
      </div>

      {err && <div className="empty">Chyba načítania dát: {err}<br />Spustil si <code>shealth ingest</code> a <code>shealth metrics</code>?</div>}

      {tab === "overview" && <Overview summary={summary} days={days} p={p} />}
      {tab === "workouts" && <Workouts data={workouts} p={p} />}
      {tab === "insights" && <Insights corr={corr} p={p} />}
      {tab === "goals" && <Goals data={goals} p={p} />}
    </div>
  );
}

function Overview({ summary, days, p }) {
  if (!summary || summary.empty) return <div className="empty">Žiadne dáta. Načítaj export a spusti metriky.</div>;
  const comps = { ...summary.components, readiness: summary.readiness };
  const kpis = (summary.kpis || []).filter((k) => k.key !== "readiness");
  return (
    <>
      <div className="grid cols-3">
        <div className="card">
          <h3>Readiness</h3>
          <p className="hint">Zotavenie na dnes · z pokojového HR, spánku, stresu a záťaže</p>
          <div className="hero">
            <ReadinessRing score={summary.readiness} p={p} />
            <ComponentBars components={comps} p={p} />
          </div>
        </div>
        <div className="grid" style={{ gridTemplateColumns: "1fr" }}>
          {kpis.slice(0, 2).map((k) => <KpiTile key={k.key} kpi={k} p={p} />)}
        </div>
        <div className="grid" style={{ gridTemplateColumns: "1fr" }}>
          {kpis.slice(2, 4).map((k) => <KpiTile key={k.key} kpi={k} p={p} />)}
        </div>
      </div>

      <div className="section-title">Trendy</div>
      <div className="grid cols-2">
        <ReadinessTrend data={days} p={p} />
        <RhrVsBaseline data={days} p={p} />
      </div>
      <div className="grid cols-2" style={{ marginTop: 14 }}>
        <SleepStages data={days} p={p} />
        <AcwrChart data={days} p={p} />
      </div>
      <div className="grid cols-2" style={{ marginTop: 14 }}>
        <TrainingLoad data={days} p={p} />
        <WeightTrend data={days} p={p} />
      </div>

      <div className="section-title">AI kouč · (Fáza 4 — čoskoro)</div>
      <div className="card">
        <div className="ai">
          <div className="avatar" />
          <div className="msg">
            Tu bude <b>AI kouč</b> (model Claude), ktorý ti z tvojich dát vysvetlí zmeny v readiness,
            navrhne tréning/regeneráciu a odpovie na otázky typu „ako mi koreluje spánok s readiness?".
            <span className="muted"> Pripája sa aj do Claude Desktop cez MCP (Fáza 5).</span>
          </div>
        </div>
      </div>
    </>
  );
}

function Workouts({ data, p }) {
  if (!data) return <div className="empty">Načítavam tréningy…</div>;
  if (!data.workouts.length) return <div className="empty">Žiadne tréningy v tomto období.</div>;
  return (
    <div className="card">
      <h3>Tréningy · posledných 90 dní</h3>
      <p className="hint">{data.workouts.length} tréningov · TRIMP = tréningový impulz z HR</p>
      <div style={{ overflowX: "auto" }}>
        <table className="wo">
          <thead>
            <tr><th>Dátum</th><th>Typ</th><th>Trvanie</th><th>Vzdial.</th><th>Tempo</th><th>Ø HR</th><th>Max HR</th><th>Kcal</th><th>TRIMP</th></tr>
          </thead>
          <tbody>
            {data.workouts.map((w, i) => (
              <tr key={i}>
                <td>{w.date}</td>
                <td><span className="tag">{w.type}</span></td>
                <td>{w.duration_min != null ? fmtDur(w.duration_min) : "–"}</td>
                <td>{w.distance_km != null ? `${w.distance_km} km` : "–"}</td>
                <td>{w.pace_min_km != null ? `${w.pace_min_km.toFixed(2)} /km` : "–"}</td>
                <td>{w.mean_hr ?? "–"}</td>
                <td>{w.max_hr ?? "–"}</td>
                <td>{w.calorie != null ? fmtNum(w.calorie) : "–"}</td>
                <td style={{ color: p.violet, fontWeight: 600 }}>{w.trimp ?? "–"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Insights({ corr, p }) {
  if (!corr) return <div className="empty">Počítam korelácie…</div>;
  return (
    <div className="grid cols-2">
      <CorrHeatmap labels={corr.labels} matrix={corr.matrix} p={p} />
      <SleepScatter data={corr.scatter} p={p} />
    </div>
  );
}

function Goals({ data, p }) {
  if (!data) return <div className="empty">Načítavam ciele…</div>;
  const colors = { steps: p.blue, sleep_minutes: p.aqua, readiness: p.violet, acwr: p.yellow };
  const fmtCur = (g) => g.key === "sleep_minutes" ? fmtDur(g.current) : g.key === "steps" ? fmtNum(g.current) : g.current;
  const fmtTgt = (g) => g.key === "sleep_minutes" ? fmtDur(g.target) : g.key === "steps" ? fmtNum(g.target) : g.target;
  return (
    <div className="grid cols-2">
      <div className="card">
        <h3>Ciele · 7-dňový priemer</h3>
        <p className="hint">Progres k cieľom vypočítaný z tvojich dát</p>
        {data.goals.map((g) => (
          <div className="goal" key={g.key}>
            <div className="g-top"><span>{g.label}</span><b>{fmtCur(g)}{g.unit ? ` ${g.unit}` : ""} / {fmtTgt(g)}</b></div>
            <div className="gbar"><i style={{ width: `${Math.min(100, (g.progress || 0) * 100)}%`, background: colors[g.key] || p.blue }} /></div>
          </div>
        ))}
      </div>
      <div className="card">
        <h3>Streak</h3>
        <p className="hint">Dni po sebe s ≥ 10 000 krokmi</p>
        <div style={{ fontSize: 52, fontWeight: 680, letterSpacing: -1, color: p.aqua }}>{data.steps_streak}</div>
        <div className="muted">dní v rade</div>
      </div>
    </div>
  );
}
