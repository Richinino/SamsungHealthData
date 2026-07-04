# Tutoriál — od nuly po bežiaci dashboard

Návod, ako dostať dáta zo Samsung Health / Galaxy Watch Ultra do projektu a spustiť celý
dashboard u seba na počítači. Všetko beží **lokálne** — dáta neopúšťajú tvoj stroj.

---

## 0) Predpoklady (nainštaluj raz)

- **Python 3.11+** — https://www.python.org/downloads/
- **Node.js 18+** (kvôli frontendu) — https://nodejs.org/
- **git** — https://git-scm.com/
- **uv** (rýchly Python správca; odporúčané) — https://docs.astral.sh/uv/getting-started/installation/
  - macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Windows (PowerShell): `irm https://astral.sh/uv/install.ps1 | iex`

> Bez `uv` to ide tiež — všade, kde je nižšie `uv run X`, môžeš použiť `python -m X`
> vo vlastnom virtualenv (`python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`).

---

## 1) Stiahni projekt

```bash
git clone https://github.com/Richinino/SamsungHealthData.git
cd SamsungHealthData
uv venv --python 3.11
uv pip install -e ".[dev]"
```

---

## 2) Rýchly štart s DEMO dátami (bez tvojho exportu)

Ak si chceš len pozrieť, ako to vyzerá, vygeneruj syntetický export a spusti to:

```bash
uv run python scripts/gen_synthetic_export.py --days 90 --out data/synthetic_export.zip
uv run shealth ingest data/synthetic_export.zip
uv run shealth metrics
(cd web && npm install && npm run build)
uv run shealth serve
```

Otvor **http://127.0.0.1:8000** v prehliadači. Hotovo. 🎉
Keď budeš mať reálny export, pokračuj krokom 3.

---

## 3) Získaj svoje reálne dáta zo Samsung Health

Dáta sa exportujú z **telefónu** (nie priamo z hodiniek — hodinky ich synchronizujú do
appky Samsung Health v telefóne).

1. V telefóne otvor **Samsung Health**.
2. Choď do **Settings** (Nastavenia) — ikonka ozubeného kolieska alebo menu „☰".
3. Nájdi **Download personal data** (staršie verzie: *Personal data → Download*).
4. Potvrď a počkaj, kým sa export vytvorí.
5. Export nájdeš v telefóne cez **My Files → Internal storage → Samsung Health →
   `samsunghealth_<meno>_<časová_pečiatka>/`**. Obsahuje veľa `.csv` súborov a
   priečinok `jsons/`.
6. **Zabaľ celý ten priečinok do ZIP** (v My Files: podrž priečinok → Compress / Zip),
   alebo appka ti rovno vytvorí ZIP.
7. **Prenes ZIP do počítača** (USB kábel, alebo cez cloud — Google Drive / Dropbox).

---

## 4) Vlož svoj export do projektu a spusti

Skopíruj svoj ZIP do priečinka `data/` v projekte a premenuj na `export.zip`
(alebo nechaj vlastný názov a použi ho v príkaze):

```bash
# skopíruj svoj súbor sem: data/export.zip

uv run shealth ingest data/export.zip     # export → DuckDB (data/health.duckdb)
uv run shealth metrics                     # dopočíta readiness, load, sleep debt, …
(cd web && npm install && npm run build)   # frontend (stačí raz; pri ďalšom spustení preskoč)
uv run shealth serve                       # → http://127.0.0.1:8000
```

Otvor **http://127.0.0.1:8000**. Dashboard beží na tvojich dátach.

> **Aktualizácia dát neskôr:** urob nový export z telefónu, nahraď `data/export.zip`
> a spusti znova `uv run shealth ingest data/export.zip && uv run shealth metrics`.
> Frontend už nemusíš buildiť.

---

## 5) Prispôsobenie výpočtov (voliteľné)

Readiness/TRIMP používajú pár parametrov, ktoré si vieš doladiť podľa seba:

```bash
uv run shealth metrics --sex male --hr-max 190 --target-sleep-min 480
```

- `--hr-max` — tvoje maximálne HR (ak nepoznáš, orientačne `220 − vek`).
- `--target-sleep-min` — cieľ spánku v minútach (480 = 8 h).
- `--sex` — `male`/`female` (mierne mení TRIMP vzorec).

---

## Časté problémy

| Problém | Riešenie |
|---|---|
| `shealth: command not found` | Používaj `uv run shealth …` (alebo aktivuj virtualenv). |
| Dashboard je prázdny / „Žiadne dáta" | Spustil si `ingest` aj `metrics`? Skontroluj, že `data/health.duckdb` existuje. |
| Port 8000 obsadený | `uv run shealth serve --port 8080` a otvor `:8080`. |
| Chyba pri `npm run build` | Over `node -v` (≥ 18). Skús `cd web && rm -rf node_modules && npm install`. |
| Export má iné stĺpce / chýbajú tabuľky | Samsung občas mení schému — pošli mi vzorku a doladím parser. |

---

## Čo bude ďalej

- **Fáza 4 — AI kouč**: nastavíš `ANTHROPIC_API_KEY` a Claude ti bude z dát robiť insighty
  a odpovedať na otázky (placeholder už v dashboarde vidíš).
- **Fáza 5 — Claude Desktop (MCP)**: pripojíš dáta priamo do Claude Desktop, nech ich vieš
  referovať v chatoch. Návod na `claude_desktop_config.json` je v `README.md`.
