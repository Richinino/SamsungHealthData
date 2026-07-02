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

# 4) testy
uv run pytest -q
```

Výsledok ingestu je `data/health.duckdb` s normalizovanými tabuľkami
(`heart_rate`, `steps_daily`, `sleep`, `sleep_stage`, `stress`, `spo2`, `exercise`,
`body_composition`, …).

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
  api/         # (Fáza 3) FastAPI backend
  ai/          # (Fáza 4) LLM kouč + ML forecast/anomaly
  mcp_server.py# (Fáza 5) MCP server pre Claude Desktop
web/           # (Fáza 3) Vite + React + Recharts dashboard
scripts/gen_synthetic_export.py
tests/
data/          # export.zip + health.duckdb (gitignored)
```

## Roadmap

- [x] **Fáza 1** — ingest: export → DuckDB, syntetické dáta, testy
- [ ] **Fáza 2** — derived metrics engine (recovery, training load, sleep debt, HRV baseline)
- [ ] **Fáza 3** — FastAPI + React/Recharts dashboard
- [ ] **Fáza 4** — AI: LLM kouč (Anthropic) + ML forecast/anomaly
- [ ] **Fáza 5** — MCP server pre Claude Desktop
- [ ] **Neskôr** — live ingest cez Samsung Health Data SDK / Health Connect; raw PPG/ECG cez Privileged SDK
