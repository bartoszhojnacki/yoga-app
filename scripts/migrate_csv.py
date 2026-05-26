"""Jednorazowa migracja istniejących CSV (v1 Streamlit) → data/*.json.

Uruchom raz po przejściu na v2:
    cd scripts && python migrate_csv.py

Tagi style/focus (joga) i type/body (mobility) są pre-computed z tytułu+opisu.
Plik można usunąć po pomyślnej migracji.
"""

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from sources import (
    MOBILITY_BODY,
    MOBILITY_TYPE,
    YOGA_FOCUS,
    YOGA_STYLE,
    match_tags,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
YOGA_CSV = REPO_ROOT / "yoga_library.csv"
MOBILITY_CSV = REPO_ROOT / "mobility.csv"
YOGA_JSON = REPO_ROOT / "data" / "yoga.json"
MOBILITY_JSON = REPO_ROOT / "data" / "mobility.json"


def extract_video_id(url: str) -> str:
    m = re.search(r"v=([A-Za-z0-9_-]+)", url or "")
    return m.group(1) if m else ""


def to_int(value: str, default: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def migrate_yoga() -> int:
    if not YOGA_CSV.exists():
        print(f"⚠️ {YOGA_CSV} nie istnieje, pomijam.")
        return 0
    videos = []
    seen = set()
    with YOGA_CSV.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            vid = extract_video_id(row.get("url", ""))
            if not vid or vid in seen:
                continue
            seen.add(vid)
            text = f"{row.get('title', '')} {row.get('description', '')} {row.get('category', '')}".lower()
            videos.append(
                {
                    "id": vid,
                    "title": row.get("title", "").strip(),
                    "channel": row.get("channel", "").strip(),
                    "duration": to_int(row.get("duration", "0"), 0),
                    "url": row.get("url", "").strip(),
                    "description": row.get("description", "").strip(),
                    "intensity": to_int(row.get("intensity", "3"), 3),
                    "props": (row.get("props") or "Brak").strip() or "Brak",
                    "style": match_tags(text, YOGA_STYLE) or ["Spokojna / Yin"],
                    "focus": match_tags(text, YOGA_FOCUS) or ["Całe ciało"],
                }
            )
    YOGA_JSON.parent.mkdir(parents=True, exist_ok=True)
    YOGA_JSON.write_text(
        json.dumps(
            {
                "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "videos": videos,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return len(videos)


def migrate_mobility() -> int:
    if not MOBILITY_CSV.exists():
        print(f"⚠️ {MOBILITY_CSV} nie istnieje, pomijam.")
        return 0
    videos = []
    seen = set()
    with MOBILITY_CSV.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            vid = extract_video_id(row.get("url", ""))
            if not vid or vid in seen:
                continue
            seen.add(vid)
            text = f"{row.get('title', '')} {row.get('description', '')}".lower()
            videos.append(
                {
                    "id": vid,
                    "title": row.get("title", "").strip(),
                    "channel": row.get("channel", "").strip(),
                    "duration": to_int(row.get("duration", "0"), 0),
                    "url": row.get("url", "").strip(),
                    "description": row.get("description", "").strip(),
                    "type_tags": match_tags(text, MOBILITY_TYPE) or ["Mobility"],
                    "body_tags": match_tags(text, MOBILITY_BODY) or ["Całe ciało"],
                }
            )
    MOBILITY_JSON.parent.mkdir(parents=True, exist_ok=True)
    MOBILITY_JSON.write_text(
        json.dumps(
            {
                "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "videos": videos,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return len(videos)


if __name__ == "__main__":
    y = migrate_yoga()
    m = migrate_mobility()
    print(f"✅ joga: {y} filmów → {YOGA_JSON.relative_to(REPO_ROOT)}")
    print(f"✅ mobility: {m} filmów → {MOBILITY_JSON.relative_to(REPO_ROOT)}")
