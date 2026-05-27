# Studio Ruchu — handout operatora

Notatka „dla siebie za pół roku”. Jak to działa, jak obsługiwać, gdzie co leży,
na co uważać. Setup od zera jest w [README.md](README.md) — tu jest obsługa.

---

## 1. Co to jest

Statyczna aplikacja webowa (HTML + Alpine.js, **bez backendu**) do wybierania
treningów jogi / mobility / (p)rehab z biblioteki filmów YouTube. Trzy zakładki,
filtry, presety „szybki wybór”, losowanie, ulubione. Hostowana na GitHub Pages.
Dane (lista filmów + tagi) generuje cykliczny GitHub Action z YouTube + OpenAI.

**Filozofia:** zero serwera, zero bazy, zero kosztów stałych. Wszystko to pliki
JSON commitowane do repo; przeglądarka je czyta. Ulubione/licznik użycia żyją w
`localStorage` urządzenia (single-user, brak logowania).

Stan na 2026-05-27: **Joga 1187 · Mobility 46 · (P)rehab 1015** (+ ~718 ID w cache odrzuceń).

---

## 2. Linki

| Co | Gdzie |
| --- | --- |
| Aplikacja (live) | https://bartoszhojnacki.github.io/yoga-app/ |
| Repo | https://github.com/bartoszhojnacki/yoga-app |
| Actions (cron + ręczne odpalenie) | https://github.com/bartoszhojnacki/yoga-app/actions |
| Sekrety | https://github.com/bartoszhojnacki/yoga-app/settings/secrets/actions |
| GH Pages settings | https://github.com/bartoszhojnacki/yoga-app/settings/pages |
| Lokalne repo | `/Users/bhojnacki/Desktop/projects/prv/yoga-app` |

---

## 3. Jak działa pipeline danych

```
YouTube (8 kanałów)
   │  fetch przez playlistItems (trick UC→UU = uploads playlist, tanie)
   │  pomija: ID już w bazie  ∪  ID w data/_rejected.json
   ▼
nowe filmy (>2 min)
   │
   ├─ Joga + (P)rehab → OpenAI (gpt-4o-mini):
   │     is_practice? intensity 1-5? czysty opis? sprzęt?
   │     • is_practice=false → ląduje w data/_rejected.json (cache)
   │     • is_practice=true  → + tagi keyword (style/focus lub type/body)
   │
   └─ Mobility (Malva) → tylko tagi keyword, bez AI
   ▼
data/{yoga,mobility,movement}.json  +  data/_rejected.json
   │  git commit + push (robi to Action albo Ty lokalnie)
   ▼
GitHub Pages rebuild → appka świeża
```

**Cache odrzuceń** (`data/_rejected.json`) to klucz do taniości: raz odrzucony
film nigdy więcej nie idzie do OpenAI. Bez niego każdy run płaciłby za te same
vlogi/tutoriale (gpt-4o-mini jest niedeterministyczny, ~16% filmów potrafi się
przerzucić reject↔accept między runami — cache to zamraża).

---

## 4. Cykliczne odnawianie (automat)

Działa samo. `.github/workflows/update-data.yml`:
- **Cron:** niedziela 06:00 UTC (08:00 latem / 07:00 zimą).
- **Ręcznie:** Actions → „Update video library” → Run workflow.
- Po sukcesie bot commituje zmiany w `data/` i pushuje → GH Pages się przebudowuje.
- Zabezpieczenia: concurrency guard (brak nakładających się runów), 60 min timeout,
  check obecności sekretów (czytelny błąd jak ich brak).

Sekrety (już ustawione): `YOUTUBE_API_KEY`, `OPENAI_API_KEY`.

---

## 5. Typowe operacje

### Odświeżyć dane ręcznie z Maca
```bash
cd /Users/bhojnacki/Desktop/projects/prv/yoga-app
source .venv/bin/activate
python3 scripts/update_data.py
git add data/ && git commit -m "data: refresh" && git push
```
(GH Pages rebuild ~1 min; w Brave hard refresh albo zamknij-otwórz ikonkę.)

### Dodać / usunąć kanał YouTube
Edytuj `scripts/sources.py`:
- Joga → `YOGA_CHANNELS`, Malva-style → `MOBILITY_CHANNELS`, (p)rehab/movement → `MOVEMENT_CHANNELS`.
- Wartość: `"Nazwa": "UCxxxx"` albo z limitem `"Nazwa": ("UCxxxx", 500)` (ostatnie N filmów).
- Channel ID bierzesz z URL kanału lub przez API. Commit + push → następny run zassie.

### Zmienić sposób klasyfikacji AI
Prompty w `scripts/update_data.py`: `YOGA_PROMPT` i `MOVEMENT_PROMPT`.
Jeśli chcesz, żeby zmiana dotknęła też filmów już odrzuconych — skasuj
`data/_rejected.json` i odpal pipeline (przeklasyfikuje wszystko od nowa).

### Poprawić źle sklasyfikowany film
`data/*.json` to zwykły JSON. Znajdź po tytule, zmień ręcznie `intensity` /
`style` / `focus` / `type_tags` / `body_tags`, commit. Pipeline **nie nadpisuje**
istniejących wpisów — tylko dodaje nowe, więc Twoja korekta przetrwa.

### Zmienić presety „szybki wybór”
`assets/app.js` → tablica `PRESETS` (każdy ma `tab`, `icon`, `label`, `apply`).

---

## 6. Instalacja na iPadzie

W **Brave** (nie Safari — bo Safari WebView nie da Shields/adblock na YT):
1. Brave → wejdź na URL appki.
2. Share → **Add to Home Screen**.
3. Klik w ikonkę = appka; „▶ Oglądaj” otwiera YT w tej samej Brave z aktywnymi
   Shields (bez reklam).

---

## 7. Backup / wersja v1 (Streamlit)

Pierwotna appka Streamlit żyje na branchu i tagu:
```bash
git checkout legacy-streamlit  # pełny kod v1 + WIP CSV-ki
git checkout v1-streamlit       # czysty stan v1
```
Powrót na nową wersję: `git checkout main`.

---

## 8. Mapa plików

```
index.html                          # cała struktura UI (3 zakładki)
assets/
  app.js                            # logika: filtry, presety, ulubione, fetch JSON
  style.css                         # styl (dark/light auto, tablet-first)
  alpine.min.js                     # Alpine.js inline (NIE z CDN — patrz §9)
data/
  yoga.json / mobility.json / movement.json   # biblioteki (auto-gen)
  _rejected.json                    # cache ID odrzuconych przez AI
scripts/
  sources.py                        # kanały + taksonomia tagów (EDYTUJESZ TU)
  update_data.py                    # pipeline YouTube→OpenAI→JSON (EDYTUJESZ TU)
  migrate_csv.py                    # jednorazowa migracja v1, raczej martwy
  requirements.txt                  # deps pipeline'u (httpx pinned, patrz §9)
.github/workflows/update-data.yml   # cron + auto-commit
README.md                           # setup od zera
HANDOUT.md                          # ten plik
```

---

## 9. Gotchas (rzeczy które nas ugryzły — nie powtarzaj)

- **Alpine z CDN nie ładuje się w Brave** — Shields blokuje 3rd-party CDN.
  Dlatego `alpine.min.js` jest inline w repo (same-origin). Nie wracaj na CDN.
- **Kolejność `<script>` w index.html ma znaczenie** — `app.js` musi być PRZED
  `alpine.min.js`. Inaczej Alpine startuje (microtask) zanim zarejestruje się
  listener `alpine:init` → „studio is not defined”. Komponent rejestrowany przez
  `Alpine.data("studio", …)`, w HTML `x-data="studio"` (bez nawiasów).
- **GitHub Pages agresywnie cache'uje** — po pushu rób hard refresh (Cmd+Shift+R)
  albo DevTools → Network → Disable cache. Cache-bust: dopisz `?v=2` do URL.
- **openai SDK vs httpx** — `openai==1.54.0` przekazuje `proxies`, którego nowy
  httpx (≥0.28) nie przyjmuje. Dlatego `httpx==0.27.2` jest zapinowane w
  requirements. Jak bumpniesz openai, sprawdź czy pin nadal potrzebny.
- **gpt-4o-mini jest niedeterministyczny** — ta sama lista filmów daje różne
  is_practice między runami. Cache odrzuceń zamraża werdykty. Jak zacznie
  przeszkadzać: niższa temperatura, model gpt-4o, albo ręczna korekta JSON.
- **Squat University = 2 filmy celowo** — to kanał edukacyjny (tutoriale, nie
  follow-along), filtr is_practice słusznie odrzuca ~wszystko. Nie „naprawiaj”.

---

## 10. Koszty

- GitHub Pages, Actions (public repo = unlimited minutes), YouTube API (darmowy
  quota 10k units/dzień, pipeline mieści się z zapasem) — **0 zł**.
- OpenAI (gpt-4o-mini) — jedyny koszt. Pierwszy duży sweep movement ~$2-5.
  Kolejne runy grosze (cache odrzuceń + dedup ⇒ tylko realnie nowe filmy).
