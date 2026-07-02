// Paleta z dataviz design systému (validovaná pre light aj dark).
export const PALETTES = {
  dark: {
    page: "#0d0d0d", surface: "#1a1a19", card2: "#232322",
    text: "#ffffff", text2: "#c3c2b7", muted: "#898781",
    grid: "#2c2c2a", axis: "#383835", border: "rgba(255,255,255,0.10)",
    blue: "#3987e5", aqua: "#199e70", yellow: "#c98500", violet: "#9085e9",
    good: "#0ca30c", warning: "#fab219", critical: "#d03b3b",
  },
  light: {
    page: "#f9f9f7", surface: "#fcfcfb", card2: "#eeede9",
    text: "#0b0b0b", text2: "#52514e", muted: "#898781",
    grid: "#e1e0d9", axis: "#c3c2b7", border: "rgba(11,11,11,0.10)",
    blue: "#2a78d6", aqua: "#1baf7a", yellow: "#eda100", violet: "#4a3aa7",
    good: "#006300", warning: "#fab219", critical: "#d03b3b",
  },
};

export function applyTheme(name) {
  const p = PALETTES[name];
  const root = document.documentElement;
  root.setAttribute("data-theme", name);
  for (const [k, v] of Object.entries(p)) root.style.setProperty(`--${k}`, v);
}

// stav podľa readiness/skóre → status farba
export function statusColor(p, score) {
  if (score == null) return p.muted;
  if (score >= 75) return p.good;
  if (score >= 55) return p.yellow;
  if (score >= 40) return p.warning;
  return p.critical;
}
