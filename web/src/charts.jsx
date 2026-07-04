import React from "react";
import {
  ResponsiveContainer, AreaChart, Area, LineChart, Line, BarChart, Bar,
  ComposedChart, ScatterChart, Scatter, CartesianGrid, XAxis, YAxis, Tooltip,
  ReferenceArea, ReferenceLine, Legend, ZAxis,
} from "recharts";
import { fmtDur } from "./ui.jsx";

const dayTick = (d) => {
  if (!d) return "";
  const [, m, day] = d.split("-");
  return `${+day}.${+m}.`;
};

export function ChartCard({ title, hint, children, legend }) {
  return (
    <div className="card">
      <h3>{title}</h3>
      {hint && <p className="hint">{hint}</p>}
      {children}
      {legend && <div className="legend">{legend}</div>}
    </div>
  );
}

function Sw({ c, children }) {
  return <div className="li"><span className="sw" style={{ background: c }} />{children}</div>;
}

function tip(p) {
  return {
    contentStyle: {
      background: p.page, border: `1px solid ${p.border}`, borderRadius: 9,
      color: p.text, fontSize: 12,
    },
    labelStyle: { color: p.muted },
    itemStyle: { color: p.text },
  };
}

const axis = (p) => ({ stroke: p.axis, tick: { fill: p.muted, fontSize: 10 }, tickLine: false });

export function ReadinessTrend({ data, p }) {
  return (
    <ChartCard title="Readiness — vývoj" hint="Denné skóre zotavenia (0–100)">
      <ResponsiveContainer width="100%" height={180}>
        <AreaChart data={data} margin={{ top: 6, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={p.grid} vertical={false} />
          <XAxis dataKey="day" tickFormatter={dayTick} {...axis(p)} minTickGap={28} />
          <YAxis domain={[30, 100]} {...axis(p)} width={42} />
          <Tooltip {...tip(p)} labelFormatter={dayTick} formatter={(v) => [Math.round(v), "Readiness"]} />
          <Area type="monotone" dataKey="readiness" stroke={p.blue} strokeWidth={2} fill={p.blue} fillOpacity={0.12} />
        </AreaChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

export function RhrVsBaseline({ data, p }) {
  return (
    <ChartCard title="Pokojový HR vs. baseline" hint="Nižšie než osobný baseline = lepšie zotavenie"
      legend={<><Sw c={p.blue}>Pokojový HR</Sw><Sw c={p.muted}>Baseline (30d)</Sw></>}>
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={data} margin={{ top: 6, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={p.grid} vertical={false} />
          <XAxis dataKey="day" tickFormatter={dayTick} {...axis(p)} minTickGap={28} />
          <YAxis domain={["dataMin - 2", "dataMax + 2"]} {...axis(p)} width={42} />
          <Tooltip {...tip(p)} labelFormatter={dayTick} />
          <Line type="monotone" dataKey="resting_hr" name="Pokojový HR" stroke={p.blue} strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="rhr_baseline" name="Baseline" stroke={p.muted} strokeWidth={2} strokeDasharray="4 4" dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

export function SleepStages({ data, p }) {
  return (
    <ChartCard title="Spánok — fázy & dĺžka" hint="Hodiny podľa fáz"
      legend={<><Sw c={p.blue}>Hlboký</Sw><Sw c={p.aqua}>REM</Sw><Sw c={p.yellow}>Ľahký</Sw><Sw c={p.card2}>Bdenie</Sw></>}>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={data} margin={{ top: 6, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={p.grid} vertical={false} />
          <XAxis dataKey="day" tickFormatter={dayTick} {...axis(p)} minTickGap={20} />
          <YAxis {...axis(p)} width={42} unit="h" />
          <Tooltip {...tip(p)} labelFormatter={dayTick} formatter={(v, n) => [`${(+v).toFixed(1)} h`, n]} />
          <Bar dataKey="deep_h" name="Hlboký" stackId="s" fill={p.blue} radius={[0, 0, 0, 0]} />
          <Bar dataKey="rem_h" name="REM" stackId="s" fill={p.aqua} />
          <Bar dataKey="light_h" name="Ľahký" stackId="s" fill={p.yellow} />
          <Bar dataKey="awake_h" name="Bdenie" stackId="s" fill={p.card2} radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

export function TrainingLoad({ data, p }) {
  return (
    <ChartCard title="Tréningová záťaž (TRIMP)" hint="Denný load (stĺpce) + akútny/chronický priemer"
      legend={<><Sw c={p.violet}>Denný load</Sw><Sw c={p.blue}>Akútny (7d)</Sw><Sw c={p.muted}>Chronický (28d)</Sw></>}>
      <ResponsiveContainer width="100%" height={180}>
        <ComposedChart data={data} margin={{ top: 6, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={p.grid} vertical={false} />
          <XAxis dataKey="day" tickFormatter={dayTick} {...axis(p)} minTickGap={28} />
          <YAxis {...axis(p)} width={42} />
          <Tooltip {...tip(p)} labelFormatter={dayTick} />
          <Bar dataKey="load" name="Load" fill={p.violet} radius={[3, 3, 0, 0]} maxBarSize={14} />
          <Line type="monotone" dataKey="load_acute" name="Akútny" stroke={p.blue} strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="load_chronic" name="Chronický" stroke={p.muted} strokeWidth={2} strokeDasharray="4 4" dot={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

export function AcwrChart({ data, p }) {
  return (
    <ChartCard title="ACWR — akútny : chronický" hint="Sladké pásmo 0.8–1.3; nad 1.5 = riziko prepätia">
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={data} margin={{ top: 6, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={p.grid} vertical={false} />
          <XAxis dataKey="day" tickFormatter={dayTick} {...axis(p)} minTickGap={28} />
          <YAxis domain={[0, 2.1]} ticks={[0, 0.5, 1, 1.5, 2]} allowDataOverflow={false}
            tickFormatter={(v) => v.toFixed(1)} {...axis(p)} width={42} />
          <ReferenceArea y1={0.8} y2={1.3} fill={p.good} fillOpacity={0.12} />
          <ReferenceLine y={1.5} stroke={p.critical} strokeDasharray="3 3" />
          <Tooltip {...tip(p)} labelFormatter={dayTick} formatter={(v) => [(+v).toFixed(2), "ACWR"]} />
          <Line type="monotone" dataKey="acwr" stroke={p.yellow} strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

export function WeightTrend({ data, p }) {
  return (
    <ChartCard title="Hmotnosť & telesný tuk" hint="Trend hmotnosti (kg)">
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={data} margin={{ top: 6, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={p.grid} vertical={false} />
          <XAxis dataKey="day" tickFormatter={dayTick} {...axis(p)} minTickGap={28} />
          <YAxis domain={["dataMin - 1", "dataMax + 1"]} {...axis(p)} width={42} unit="" />
          <Tooltip {...tip(p)} labelFormatter={dayTick} />
          <Line type="monotone" dataKey="weight_ffill" name="Hmotnosť" stroke={p.aqua} strokeWidth={2} dot={false} connectNulls />
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

// ---- Insights ----
export function SleepScatter({ data, p }) {
  return (
    <ChartCard title="Spánok → readiness nasledujúci deň" hint="Každý bod = jedna noc">
      <ResponsiveContainer width="100%" height={220}>
        <ScatterChart margin={{ top: 6, right: 12, left: 0, bottom: 4 }}>
          <CartesianGrid stroke={p.grid} />
          <XAxis type="number" dataKey="sleep_h" name="Spánok" unit=" h" domain={["dataMin - 0.3", "dataMax + 0.3"]} {...axis(p)} />
          <YAxis type="number" dataKey="next_readiness" name="Readiness+1" domain={[30, 100]} {...axis(p)} width={42} />
          <ZAxis range={[50, 50]} />
          <Tooltip {...tip(p)} cursor={{ stroke: p.muted }}
            formatter={(v, n) => [n === "Spánok" ? `${v} h` : Math.round(v), n]} />
          <Scatter data={data} fill={p.blue} fillOpacity={0.7} />
        </ScatterChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

const CORR_LABELS = {
  readiness: "Readiness", resting_hr: "Pokoj. HR", sleep_minutes: "Spánok",
  sleep_debt: "Sleep debt", stress_avg: "Stres", load: "Load", steps: "Kroky", acwr: "ACWR",
};

export function CorrHeatmap({ labels, matrix, p }) {
  if (!labels || !labels.length) return null;
  const val = (x, y) => matrix.find((c) => c.x === x && c.y === y)?.v;
  const color = (v) => {
    if (v == null) return p.card2;
    // diverging blue(-) ↔ red(+), gray midpoint
    const a = Math.min(1, Math.abs(v));
    const base = v >= 0 ? p.critical : p.blue;
    return `${base}${Math.round(a * 200 + 20).toString(16).padStart(2, "0")}`;
  };
  const n = labels.length;
  return (
    <ChartCard title="Korelácie metrík" hint="Pearson r · modrá = záporná, červená = kladná">
      <div className="heat" style={{ gridTemplateColumns: `84px repeat(${n}, 1fr)` }}>
        <div />
        {labels.map((l) => <div className="hlabel" key={`h${l}`}>{CORR_LABELS[l] || l}</div>)}
        {labels.map((row) => (
          <React.Fragment key={`r${row}`}>
            <div className="hlabel" style={{ justifyContent: "flex-end", paddingRight: 6 }}>{CORR_LABELS[row] || row}</div>
            {labels.map((col) => {
              const v = val(col, row);
              return <div className="cell" key={`${row}-${col}`} style={{ background: color(v) }}
                title={`${CORR_LABELS[row]} × ${CORR_LABELS[col]}: ${v ?? "–"}`}>{v == null ? "" : v.toFixed(1)}</div>;
            })}
          </React.Fragment>
        ))}
      </div>
    </ChartCard>
  );
}
