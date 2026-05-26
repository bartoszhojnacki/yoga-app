"""Aktualizacja data/yoga.json i data/mobility.json z YouTube + OpenAI.

Uruchamiane przez .github/workflows/update-data.yml lub lokalnie:
    cd scripts && python update_data.py

Pipeline:
    1. Wczytaj istniejące data/*.json (dedup po video_id).
    2. Pobierz nowe filmy z YOGA_CHANNELS i MOBILITY_CHANNELS.
    3. Mobility: tagowanie keyword-based (sources.py taxonomy).
    4. Joga: enrichment przez OpenAI (intensity, props, tagi, czysty opis).
    5. Filmy nie-praktyki (vlogi, zapowiedzi) są pomijane przez AI.
    6. Zapisz data/*.json.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import isodate
from dotenv import load_dotenv
from googleapiclient.discovery import build
from openai import OpenAI

from sources import (
    MIN_DURATION_MIN,
    MOBILITY_BODY,
    MOBILITY_CHANNELS,
    MOBILITY_TYPE,
    YOGA_CHANNELS,
    YOGA_FOCUS,
    YOGA_STYLE,
    match_tags,
)

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
YOGA_JSON = DATA_DIR / "yoga.json"
MOBILITY_JSON = DATA_DIR / "mobility.json"

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

AI_BATCH_SIZE = 10
AI_MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = """Jesteś ekspertem jogi. Analizujesz filmy z YouTube pod kątem aplikacji fitness.
Dla każdego filmu otrzymasz: Tytuł, Czas, Opis.
Zwróć JSON z polami:
1. "is_practice" (boolean): True tylko jeśli to sesja ćwiczeń. False dla vlogów, zapowiedzi.
2. "clean_description" (string): 1-2 zdania technicznego opisu (co robimy).
3. "intensity" (integer 1-5):
   - 1: Bardzo łagodna (Yin, Nidra, Leżenie)
   - 2: Łagodna (Spokojne rozciąganie, Hatha dla początkujących)
   - 3: Umiarkowana (Standardowa Vinyasa, Flow)
   - 4: Wymagająca (Power Yoga, Strong Flow)
   - 5: Wysiłkowa (Cardio Yoga, HIIT)
4. "props" (string): Wymień wymagany sprzęt (np. "Klocki", "Pasek"). Jeśli nic nie trzeba, wpisz "Brak".
"""


def load_json(path: Path) -> dict:
    if path.exists():
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    return {"updated_at": None, "videos": []}


def save_json(path: Path, payload: dict) -> None:
    payload["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def existing_ids(data: dict) -> set[str]:
    return {v["id"] for v in data.get("videos", []) if v.get("id")}


def clean_description(text: str) -> str:
    text = re.sub(r"http\S+", "", str(text))
    text = " ".join(text.split())
    return text[:400]


def fetch_channel_videos(youtube, channel_name: str, channel_id: str, skip_ids: set[str]) -> list[dict]:
    print(f"   🔎 {channel_name}…", flush=True)
    result = []
    try:
        ch = youtube.channels().list(id=channel_id, part="contentDetails").execute()
        if not ch.get("items"):
            return result
        uploads_id = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

        request = youtube.playlistItems().list(
            playlistId=uploads_id, part="snippet", maxResults=50
        )
        while request:
            response = request.execute()
            items = response.get("items", [])
            if not items:
                break
            new_ids = [
                it["snippet"]["resourceId"]["videoId"]
                for it in items
                if it["snippet"]["resourceId"]["videoId"] not in skip_ids
            ]
            if new_ids:
                vid_res = youtube.videos().list(
                    id=",".join(new_ids), part="snippet,contentDetails"
                ).execute()
                for v in vid_res.get("items", []):
                    seconds = isodate.parse_duration(
                        v["contentDetails"]["duration"]
                    ).total_seconds()
                    minutes = int(seconds // 60)
                    if minutes < MIN_DURATION_MIN:
                        continue
                    result.append(
                        {
                            "id": v["id"],
                            "title": v["snippet"]["title"],
                            "channel": channel_name,
                            "duration": minutes,
                            "raw_description": v["snippet"]["description"].replace("\n", " "),
                            "url": f"https://www.youtube.com/watch?v={v['id']}",
                        }
                    )
            request = youtube.playlistItems().list_next(request, response)
    except Exception as e:
        print(f"      [!] Błąd kanału {channel_name}: {e}", flush=True)
    return result


def tag_mobility(video: dict) -> dict:
    text = f"{video['title']} {video.get('raw_description', '')}".lower()
    return {
        "id": video["id"],
        "title": video["title"],
        "channel": video["channel"],
        "duration": video["duration"],
        "url": video["url"],
        "description": clean_description(video.get("raw_description", "")),
        "type_tags": match_tags(text, MOBILITY_TYPE) or ["Mobility"],
        "body_tags": match_tags(text, MOBILITY_BODY) or ["Całe ciało"],
    }


def curate_yoga_batch(client: OpenAI, batch: list[dict]) -> list[dict]:
    payload = "\n---\n".join(
        f"ID: {i}\nTitle: {v['title']}\nDuration: {v['duration']}\nDesc: {v.get('raw_description', '')[:400]}"
        for i, v in enumerate(batch)
    )
    user_prompt = (
        "Format JSON: { \"videos\": [ { \"id\": 0, \"is_practice\": true, "
        "\"clean_description\": \"...\", \"intensity\": 3, \"props\": \"Brak\" } ] }\n\nDATA:\n"
        + payload
    )
    try:
        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
        ai = json.loads(response.choices[0].message.content).get("videos", [])
    except Exception as e:
        print(f"      [!] OpenAI błąd: {e}", flush=True)
        return []

    enriched = []
    for item in ai:
        idx = item.get("id")
        if idx is None or idx >= len(batch) or not item.get("is_practice", False):
            continue
        original = batch[idx]
        text = f"{original['title']} {original.get('raw_description', '')}".lower()
        enriched.append(
            {
                "id": original["id"],
                "title": original["title"],
                "channel": original["channel"],
                "duration": original["duration"],
                "url": original["url"],
                "description": item.get("clean_description") or clean_description(original.get("raw_description", "")),
                "intensity": int(item.get("intensity", 3)),
                "props": item.get("props", "Brak") or "Brak",
                "style": match_tags(text, YOGA_STYLE) or ["Spokojna / Yin"],
                "focus": match_tags(text, YOGA_FOCUS) or ["Całe ciało"],
            }
        )
    return enriched


def curate_yoga(raw_videos: list[dict]) -> list[dict]:
    if not raw_videos:
        return []
    if not OPENAI_API_KEY:
        print("   ⚠️ Brak OPENAI_API_KEY — pomijam enrichment jogi", flush=True)
        return []
    client = OpenAI(api_key=OPENAI_API_KEY)
    enriched = []
    for i in range(0, len(raw_videos), AI_BATCH_SIZE):
        batch = raw_videos[i : i + AI_BATCH_SIZE]
        print(f"   🤖 batch {i + 1}-{i + len(batch)} / {len(raw_videos)}", flush=True)
        enriched.extend(curate_yoga_batch(client, batch))
    return enriched


def main() -> int:
    if not YOUTUBE_API_KEY:
        print("❌ Brak YOUTUBE_API_KEY", flush=True)
        return 1

    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

    yoga_data = load_json(YOGA_JSON)
    mobility_data = load_json(MOBILITY_JSON)
    yoga_seen = existing_ids(yoga_data)
    mobility_seen = existing_ids(mobility_data)

    print(f"🧘 Joga w bazie: {len(yoga_seen)}", flush=True)
    raw_yoga = []
    for name, cid in YOGA_CHANNELS.items():
        raw_yoga.extend(fetch_channel_videos(youtube, name, cid, yoga_seen))
    print(f"   nowych do enrichment: {len(raw_yoga)}", flush=True)

    new_yoga = curate_yoga(raw_yoga)
    if new_yoga:
        yoga_data["videos"].extend(new_yoga)
        save_json(YOGA_JSON, yoga_data)
        print(f"✅ +{len(new_yoga)} jogi → {YOGA_JSON.name}", flush=True)
    else:
        print("💤 Brak nowości w jodze.", flush=True)

    print(f"\n🤸 Mobility w bazie: {len(mobility_seen)}", flush=True)
    raw_mobility = []
    for name, cid in MOBILITY_CHANNELS.items():
        raw_mobility.extend(fetch_channel_videos(youtube, name, cid, mobility_seen))
    new_mobility = [tag_mobility(v) for v in raw_mobility]
    if new_mobility:
        mobility_data["videos"].extend(new_mobility)
        save_json(MOBILITY_JSON, mobility_data)
        print(f"✅ +{len(new_mobility)} mobility → {MOBILITY_JSON.name}", flush=True)
    else:
        print("💤 Brak nowości w mobility.", flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
