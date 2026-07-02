# SamsungHealthData — vlastný dashboard + AI vrstva

Vlastný, **oveľa krajší dashboard** nad dátami zo **Samsung Health / Galaxy Watch Ultra**,
s viacerými **dopočítanými metrikami** (recovery, training load, sleep debt, HRV baseline…),
lepším **trackingom progresu** a **vlastnou AI vrstvou** (LLM kouč + prediktívne modely),
ktorá je lepšia než tá zabudovaná od Samsungu — plus **MCP server**, aby si tie dáta vedel
referovať priamo v **Claude Desktop** chatoch.

> Stav: **Fáza 1 — ingest pipeline** (parsovanie exportu → DuckDB) + syntetické dáta a testy.
> Ďalšie fázy (metriky, web dashboard, AI, MCP) pribúdajú postupne — viď [Roadmap](#roadmap).

---

## Ako spraviť export zo Samsung Health

1. V telefóne otvor **Samsung Health → ☰ / Settings → Download personal data** (staršie verzie:
   *Settings → Personal data → Download*).
2. Export sa uloží do
   `My Files > Internal storage > Samsung Health > samsunghealth_<user>_<timestamp>/`.
   Obsahuje množstvo `*.csv` súborov a priečinok `jsons/` (dáta vyššieho rozlíšenia — napr.
   per-minútové HR biny).
3. Zazipuj tento priečinok (alebo použij ZIP, ktorý appka vytvorí) a **skopíruj ho do
   `data/export.zip`** v tomto repe.

> ⚠️ `data/*.zip` a `data/*.duckdb` sú v `.gitignore` — **osobné dáta sa nikdy necommitujú.**

## Prehľad ciest k dátam zo Samsung Health

| Cesta | Čo dostaneš | Náročnosť |
|---|---|---|
| **Export z appky** *(používame)* | Celá história: kroky, HR (+ per-min v JSON), sleep + fázy, stress, SpO2, body composition (BIA), workouty s GPS, nutrition… | Bez schválenia, najbohatší historický objem, ale manuálny re-export. |
| **Health Connect** | Moderné Android API, ale užšia sada typov. | Treba Android appku + telefón. |
| **Samsung Health Data SDK** | Plná sada typov, read/insert/update/delete; developer mode na čítanie vlastných dát bez partner requestu. | Android appka (Java 17), telefón, Samsung Health ≥ 6.30.2. |
| **Privileged / Sensor SDK** | Raw signály z hodiniek: PPG (25 Hz), akcelerometer, ECG, IBI, HR. | Wear OS appka + **schválenie partnerom** od Samsungu. |

Starý *Samsung Health SDK for Android* je **deprecated od 31. 7. 2025** — nástupca je
*Samsung Health Data SDK*.

## Setup / spustenie

Požiadavky: Python ≥ 3.11, [`uv`](https://docs.astral.sh/uv/) (alebo pip).

```bash
# 1) prostredie + závislosti
uv venv --python 3.11
uv pip install -e ".[dev]"

# 2) vygeneruj syntetický export (na vývoj bez osobných dát)
uv run python scripts/gen_synthetic_export.py --days 90 --out data/synthetic_export.zip

# 3) načítaj export do DuckDB
uv run shealth ingest data/synthetic_export.zip
#   ...alebo tvoj reálny export:
uv run shealth ingest data/export.zip

# 4) vypočítaj odvodené denné metriky (zapíše tabuľku metrics_daily)
uv run shealth metrics --tail 7

# 5) zbuildi frontend a spusti dashboard
(cd web && npm install && npm run build)
uv run shealth serve            # → http://127.0.0.1:8000

# 6) testy
uv run pytest -q
```

Pri vývoji frontendu: `cd web && npm run dev` (Vite na :5173, proxuje `/api` na :8000,
takže bež paralelne `uv run shealth serve`).

Výsledok ingestu je `data/health.duckdb` s normalizovanými tabuľkami
(`heart_rate`, `steps_daily`, `sleep`, `sleep_stage`, `stress`, `spo2`, `exercise`,
`body_composition`, …).

## Odvodené metriky (Fáza 2)

`shealth metrics` zostaví dennú tabuľku **`metrics_daily`** s transparentnými vzorcami
(žiadna čierna skrinka) — kód v `src/shealth/metrics/`:

- **Recovery / Readiness skóre (0–100)** — vážený priemer: pokojový HR vs. osobný baseline
  (30 %), spánok (35 %), stres (20 %), tréningová záťaž/ACWR (15 %); chýbajúce zložky sa
  prenormujú (`scoring.py`).
- **Training load** — Banister **TRIMP** z workoutov + **ACWR** (7-dňový / 28-dňový load;
  sladké pásmo ≈ 0.8–1.3) (`load.py`).
- **Sleep debt** — kumulatívny deficit oproti cieľu (default 8 h) za 14 nocí; **sleep
  regularity** = smerodajná odchýlka stredu spánku (`scoring.py`).
- **Spánkové fázy** — podiel deep/rem/light/awake na noc.
- **Body-composition delta** — zmena hmotnosti za 7 / 30 dní; pokojový HR baseline; stres trend.

Parametre (pohlavie, `hr_max`, cieľ spánku) sú konfigurovateľné cez CLI alebo
`MetricParams`.

## Dashboard (Fáza 3)

Lokálny web dashboard — **FastAPI** backend (`src/shealth/api/`) číta `metrics_daily` a
surové tabuľky z DuckDB a servuje **React + Recharts** SPA (`web/`). Postavený na dataviz
design systéme (validovaná paleta, prístupné grafy), **dark aj light** téma (prepínač,
uložený v `localStorage`). Štyri taby:

- **Prehľad** — readiness ring + rozklad zložiek, KPI dlaždice so sparklinami, trendy
  (readiness, pokojový HR vs. baseline, spánkové fázy, ACWR, training load, hmotnosť).
- **Tréningy** — tabuľka workoutov (trvanie, vzdialenosť, tempo, HR, TRIMP).
- **Insights** — korelačná heatmapa metrík + scatter spánok → readiness nasledujúci deň.
- **Ciele** — progres k cieľom (7-dňový priemer) + streak dní s ≥ 10 000 krokmi.

API endpointy: `/api/summary`, `/api/timeseries`, `/api/workouts`, `/api/correlations`,
`/api/goals` (všetky s `?range=7d|30d|90d|all`).

## AI vrstva

Nastav API kľúč a spusti LLM kouča (pribúda vo Fáze 4):

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

## Pripojenie na Claude Desktop (MCP)

Po pridaní MCP servera (Fáza 5) doň pridáš dáta ako nástroje/resources. Do
`claude_desktop_config.json`:

```jsonc
{
  "mcpServers": {
    "shealth": {
      "command": "uv",
      "args": ["run", "python", "-m", "shealth.mcp_server"],
      "cwd": "/absolutna/cesta/k/SamsungHealthData",
      "env": { "SHEALTH_DB": "data/health.duckdb" }
    }
  }
}
```

Potom sa v Claude Desktop môžeš pýtať napr. *„aký bol môj HRV trend minulý týždeň?"* a
Claude si vytiahne agregáty priamo z tvojej DuckDB.

## Štruktúra repa

```
pyproject.toml
src/shealth/
  ingest/      # unzip, csv_reader, json_decode, datatypes, load
  metrics/     # (Fáza 2) recovery, training load, sleep debt, HRV baseline
  api/         # FastAPI backend (app, queries)
  ai/          # (Fáza 4) LLM kouč + ML forecast/anomaly
  mcp_server.py# (Fáza 5) MCP server pre Claude Desktop
web/           # Vite + React + Recharts dashboard (src/, dist/ po builde)
scripts/gen_synthetic_export.py
tests/
data/          # export.zip + health.duckdb (gitignored)
```

## Roadmap

- [x] **Fáza 1** — ingest: export → DuckDB, syntetické dáta, testy
- [x] **Fáza 2** — derived metrics engine (readiness, training load/ACWR, sleep debt, regularita)
- [x] **Fáza 3** — FastAPI + React/Recharts dashboard (dark/light, 4 taby)
- [ ] **Fáza 4** — AI: LLM kouč (Anthropic) + ML forecast/anomaly
- [ ] **Fáza 5** — MCP server pre Claude Desktop
- [ ] **Neskôr** — live ingest cez Samsung Health Data SDK / Health Connect; raw PPG/ECG cez Privileged SDK
