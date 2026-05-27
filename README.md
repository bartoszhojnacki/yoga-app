# Studio Ruchu

Statyczna appka (HTML + Alpine.js) do wybierania treningów jogi i mobility z biblioteki YouTube. Działa w przeglądarce, hostowana na GitHub Pages, aktualizowana raz w tygodniu przez GitHub Action.

## Stack

- **Front:** vanilla HTML/CSS + [Alpine.js](https://alpinejs.dev) z CDN, bez build stepa.
- **Dane:** `data/yoga.json` + `data/mobility.json` (zbundlowane z appką).
- **Backend update:** Python script (`scripts/update_data.py`) wywoływany przez cron w GitHub Action — pobiera nowe filmy z YouTube, joga przechodzi przez OpenAI (intensity/props/clean description), mobility taguje keyword-based.
- **Preferencje (ulubione, licznik użycia):** localStorage przeglądarki.

## Setup (jednorazowo)

### 1. Sekrety GitHub

Settings → Secrets and variables → Actions → New repository secret:

| Secret | Wartość |
| --- | --- |
| `YOUTUBE_API_KEY` | YouTube Data API v3 key ([console.cloud.google.com](https://console.cloud.google.com)) |
| `OPENAI_API_KEY` | OpenAI API key — używany tylko do enrichment jogi |

### 2. GitHub Pages

Settings → Pages → Source: **Deploy from a branch** → Branch: **main** / Folder: **/ (root)** → Save.

Po pierwszym deployu URL będzie: `https://<username>.github.io/yoga-app/`.

### 3. Pierwszy update danych

Actions → "Update video library" → Run workflow. Albo poczekaj do najbliższej niedzieli 06:00 UTC.

## Instalacja na iPad (Brave)

Cel: appka uruchamiana z ikony na home screen, filmy YT otwierane w Brave (Shields blokuje reklamy).

1. Otwórz **Brave** (App Store).
2. Wejdź na URL appki (`https://<username>.github.io/yoga-app/`).
3. Stuknij ikonę "Share" w Brave → **Add to Home Screen**.
4. Ikona Brave-shortcut pojawi się na home screen. Stuknięcie odpala Brave z appką.
5. Klik "▶ Oglądaj" otwiera YouTube w nowej karcie Brave — Shields aktywny, brak reklam.

> Nie używaj "Add to Home Screen" z **Safari** — odpali w Safari WebView i Brave Shields nie zadziała na filmach YT.

## Edycja źródeł

- **Kanały YouTube:** `scripts/sources.py` → `YOGA_CHANNELS`, `MOBILITY_CHANNELS`.
- **Słowa kluczowe tagów:** `scripts/sources.py` → `YOGA_STYLE`, `YOGA_FOCUS`, `MOBILITY_TYPE`, `MOBILITY_BODY`. Tagi w istniejących wpisach NIE zostaną przeliczone wstecznie — kolejne uruchomienie cron'a otaguje tylko nowe filmy. Jeśli chcesz przeliczyć wszystko, usuń `data/*.json` i odpal `python scripts/migrate_csv.py` (wymaga starych CSV-ek z `legacy-streamlit`).
- **Presety "Szybki wybór":** `assets/app.js` → tablica `PRESETS`.

## Lokalne uruchomienie

```bash
# Front:
python3 -m http.server 8000
# → http://localhost:8000

# Test pipeline updatu (wymaga .env z YOUTUBE_API_KEY i OPENAI_API_KEY):
cd scripts && python update_data.py
```

## Backup wersji v1 (Streamlit)

Stara wersja jest dostępna na branchu `legacy-streamlit` i tagu `v1-streamlit`:

```bash
git checkout legacy-streamlit  # cały kod + WIP
git checkout v1-streamlit      # stan v1 bez WIP
```

## Struktura

```
.github/workflows/update-data.yml   # cron Action (niedziela 06:00 UTC) + manual
data/
  yoga.json                         # auto-generated
  mobility.json                     # auto-generated
  movement.json                     # auto-generated ((p)rehab / movement)
  _rejected.json                    # cache: ID odrzucone przez AI (is_practice=false)
scripts/
  sources.py                        # kanały (YOGA/MOBILITY/MOVEMENT) + taksonomia
  update_data.py                    # pipeline (YouTube → OpenAI → JSON)
  migrate_csv.py                    # jednorazowa migracja v1 CSV → JSON
  requirements.txt
assets/
  app.js                            # Alpine.js logic + presety
  style.css
index.html
```

## Cache odrzuceń (`data/_rejected.json`)

Filmy, które AI oznaczy jako nie-praktykę (`is_practice=false` — vlogi, tutoriale,
zapowiedzi), lądują w `data/_rejected.json`. Przy każdym kolejnym uruchomieniu
pipeline pomija te ID, więc **nie płacisz drugi raz za OpenAI** na tych samych
śmieciach i klasyfikacja jest deterministyczna (nie wpadają losowo przy re-skanie).

Plik jest commitowany do repo (cron na świeżym checkoucie też musi go widzieć).
Jeśli chcesz wymusić ponowną ocenę odrzuconych (np. po zmianie promptu), usuń
`data/_rejected.json` i odpal pipeline ponownie.
