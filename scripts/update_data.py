"""Aktualizacja data/yoga.json, data/mobility.json, data/movement.json.

Uruchamiane przez .github/workflows/update-data.yml lub lokalnie:
    python scripts/update_data.py

Pipeline:
    1. Wczytaj istniejące data/*.json (dedup po video_id).
    2. Pobierz nowe filmy z YOGA / MOBILITY / MOVEMENT channels.
       Trick UC→UU eliminuje channels.list() call (uploads playlist ID
       to channel ID z 'UC' zamienionym na 'UU').
    3. Joga + Movement: enrichment przez OpenAI (is_practice + intensity
       + clean_description + props), z dedykowanymi promptami.
    4. Mobility (Malva): tagowanie keyword-based bez AI.
    5. Zapisz data/*.json.
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
    MOVEMENT_BODY,
    MOVEMENT_CHANNELS,
    MOVEMENT_TYPE,
    YOGA_CHANNELS,
    YOGA_FOCUS,
    YOGA_STYLE,
    channel_iter,
    match_tags,
)

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
YOGA_JSON = DATA_DIR / "yoga.json"
MOBILITY_JSON = DATA_DIR / "mobility.json"
MOVEMENT_JSON = DATA_DIR / "movement.json"

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

AI_BATCH_SIZE = 10
AI_MODEL = "gpt-4o-mini"

YOGA_PROMPT = """Jesteś ekspertem jogi. Analizujesz filmy z YouTube pod kątem aplikacji fitness.
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

MOVEMENT_PROMPT = """You are an expert in mobility, (p)rehab, and movement training.
You analyze YouTube videos for a personal practice app.
For each video you receive: Title, Duration (minutes), Description (English).
Return JSON with these fields per video:
1. "is_practice" (boolean): True ONLY if this is an actual workout/practice session
   the viewer is meant to follow along with (mobility flow, stretching routine,
   prehab exercises, strength session, movement flow). False for:
   - Pure tutorials / form breakdowns / "how to fix X" without exercises to follow
   - Vlogs, podcasts, interviews, Q&A
   - Trailers, announcements, channel intros
   - Pure educational content ("STOP doing this", "5 mistakes...")
   Borderline case: short follow-along routine with brief explanation = True.
2. "clean_description" (string): 1-2 sentences, English OK, what the viewer will do.
3. "intensity" (integer 1-5):
   - 1: Very gentle (passive stretching, breathwork, restorative)
   - 2: Gentle (slow mobility, basic flexibility, beginner prehab)
   - 3: Moderate (standard mobility flow, active stretching)
   - 4: Demanding (strength-focused mobility, intense flexibility work, animal flow)
   - 5: High exertion (full strength workout, conditioning, intense flow)
4. "props" (string): Required equipment, e.g. "Resistance band", "Foam roller",
   "Yoga blocks", "Pull-up bar". If nothing needed, write "Brak".
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


def uploads_playlist_id(channel_id: str) -> str:
    """UC→UU trick — uploads playlist ID = channel ID z UC zamienionym na UU."""
    if not channel_id.startswith("UC"):
        raise ValueError(f"Unexpected channel ID format: {channel_id}")
    return "UU" + channel_id[2:]


def fetch_channel_videos(
    youtube,
    channel_name: str,
    channel_id: str,
    skip_ids: set[str],
    max_videos: int | None = None,
) -> list[dict]:
    cap_str = f" (cap {max_videos})" if max_videos else ""
    print(f"   🔎 {channel_name}{cap_str}…", flush=True)
    result = []
    scanned = 0
    try:
        request = youtube.playlistItems().list(
            playlistId=uploads_playlist_id(channel_id),
            part="snippet",
            maxResults=50,
        )
        while request:
            response = request.execute()
            items = response.get("items", [])
            if not items:
                break
            scanned += len(items)
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
            if max_videos is not None and scanned >= max_videos:
                break
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


def curate_batch(client: OpenAI, batch: list[dict], system_prompt: str) -> list[dict]:
    """Wspólna ścieżka AI dla yoga i movement — różni się tylko promptem i
    post-processingiem tagów (style/focus vs type/body). Zwraca raw AI items."""
    payload = "\n---\n".join(
        f"ID: {i}\nTitle: {v['title']}\nDuration: {v['duration']}\nDesc: {v.get('raw_description', '')[:400]}"
        for i, v in enumerate(batch)
    )
    user_prompt = (
        "Return JSON: { \"videos\": [ { \"id\": 0, \"is_practice\": true, "
        "\"clean_description\": \"...\", \"intensity\": 3, \"props\": \"Brak\" } ] }\n\nDATA:\n"
        + payload
    )
    try:
        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content).get("videos", [])
    except Exception as e:
        print(f"      [!] OpenAI błąd: {e}", flush=True)
        return []


def curate(
    raw_videos: list[dict],
    system_prompt: str,
    primary_taxonomy: dict,
    primary_key: str,
    secondary_taxonomy: dict,
    secondary_key: str,
    fallback_primary: str,
    fallback_secondary: str,
) -> list[dict]:
    """Generic AI enrichment. Stosuje match_tags na dwóch taksonomiach
    (np. style+focus dla jogi, type+body dla movement)."""
    if not raw_videos:
        return []
    if not OPENAI_API_KEY:
        print("   ⚠️ Brak OPENAI_API_KEY — pomijam enrichment", flush=True)
        return []
    client = OpenAI(api_key=OPENAI_API_KEY)
    enriched = []
    for i in range(0, len(raw_videos), AI_BATCH_SIZE):
        batch = raw_videos[i : i + AI_BATCH_SIZE]
        print(f"   🤖 batch {i + 1}-{i + len(batch)} / {len(raw_videos)}", flush=True)
        ai_items = curate_batch(client, batch, system_prompt)
        for item in ai_items:
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
                    primary_key: match_tags(text, primary_taxonomy) or [fallback_primary],
                    secondary_key: match_tags(text, secondary_taxonomy) or [fallback_secondary],
                }
            )
    return enriched


def process_channels(
    youtube,
    label: str,
    channels: dict,
    existing: set[str],
    enrich_fn,
    out_path: Path,
    out_data: dict,
) -> int:
    print(f"\n{label} w bazie: {len(existing)}", flush=True)
    raw = []
    for name, cid, cap in channel_iter(channels):
        raw.extend(fetch_channel_videos(youtube, name, cid, existing, cap))
    print(f"   nowych do enrichment: {len(raw)}", flush=True)
    enriched = enrich_fn(raw)
    if enriched:
        out_data["videos"].extend(enriched)
        save_json(out_path, out_data)
        print(f"✅ +{len(enriched)} → {out_path.name}", flush=True)
    else:
        print(f"💤 Brak nowości w {out_path.stem}.", flush=True)
    return len(enriched)


def main() -> int:
    if not YOUTUBE_API_KEY:
        print("❌ Brak YOUTUBE_API_KEY", flush=True)
        return 1

    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

    yoga_data = load_json(YOGA_JSON)
    mobility_data = load_json(MOBILITY_JSON)
    movement_data = load_json(MOVEMENT_JSON)

    # JOGA — AI enrichment (style + focus)
    process_channels(
        youtube,
        "🧘 Joga",
        YOGA_CHANNELS,
        existing_ids(yoga_data),
        lambda raw: curate(
            raw, YOGA_PROMPT,
            YOGA_STYLE, "style",
            YOGA_FOCUS, "focus",
            "Spokojna / Yin", "Całe ciało",
        ),
        YOGA_JSON,
        yoga_data,
    )

    # MOBILITY (Malva) — keyword tagging, bez AI
    print(f"\n🤸 Mobility (Malva) w bazie: {len(existing_ids(mobility_data))}", flush=True)
    raw_mobility = []
    for name, cid, _ in channel_iter(MOBILITY_CHANNELS):
        raw_mobility.extend(fetch_channel_videos(youtube, name, cid, existing_ids(mobility_data)))
    new_mobility = [tag_mobility(v) for v in raw_mobility]
    if new_mobility:
        mobility_data["videos"].extend(new_mobility)
        save_json(MOBILITY_JSON, mobility_data)
        print(f"✅ +{len(new_mobility)} → mobility.json", flush=True)
    else:
        print("💤 Brak nowości w mobility.", flush=True)

    # MOVEMENT / (P)rehab — AI enrichment (type + body)
    process_channels(
        youtube,
        "🦾 Movement / (P)rehab",
        MOVEMENT_CHANNELS,
        existing_ids(movement_data),
        lambda raw: curate(
            raw, MOVEMENT_PROMPT,
            MOVEMENT_TYPE, "type_tags",
            MOVEMENT_BODY, "body_tags",
            "Mobility", "Całe ciało / Full body",
        ),
        MOVEMENT_JSON,
        movement_data,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
