// Klient pre /api endpointy backendu.
async function get(path, range) {
  const q = range ? `?range=${range}` : "";
  const r = await fetch(`/api${path}${q}`);
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return r.json();
}

export const api = {
  summary: (range) => get("/summary", range),
  timeseries: (range) => get("/timeseries", range),
  workouts: (range) => get("/workouts", range),
  correlations: (range) => get("/correlations", range),
  goals: () => get("/goals"),
};
