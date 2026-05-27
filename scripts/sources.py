"""Konfiguracja źródeł danych i taksonomii tagów.

Zmień YOGA_CHANNELS / MOBILITY_CHANNELS / MOVEMENT_CHANNELS żeby
dodać/usunąć kanały YouTube. Wartość w słowniku to channel ID albo
tuple (channel_id, max_videos) jeśli chcemy ograniczyć ilość ostatnich
filmów do pobrania (np. dla gigantycznych kanałów).

Słowniki keywords używane są do auto-tagowania (mobility) oraz do
enrichment wyników AI (yoga, movement).
"""

YOGA_CHANNELS = {
    "Małgorzata Mostowska": "UCITlHzj4MUzRNM17pdWUWeQ",
    "Yoga Home": "UCUVNvkkzMrT4qMhlql2t4iQ",
}

MOBILITY_CHANNELS = {
    "Malva Stretching": "UCIJA9AD3fxbDNwARNBww5mg",
}

# Movement / (P)rehab — anglojęzyczne, AI klasyfikuje is_practice + intensity.
# Wartość: channel_id albo (channel_id, max_recent_videos) dla limitu.
MOVEMENT_CHANNELS = {
    "Tom Merrick": "UCU0DZhN-8KFLYO6beSaYljg",
    "mobility by julia reppel": "UCjnHdA1-dtgx4xVA9QjIz7g",
    "Squat University": ("UCyPYQTT20IgzVw92LDvtClw", 500),
    "[P]rehab": "UCZOrpZTHi21RZpnxXdlJbgQ",
    "MovementbyDavid": "UCM2ra7Od2jliHB9TLPKt76w",
}

MIN_DURATION_MIN = 2

YOGA_STYLE = {
    "Spokojna / Yin": ["yin", "spokojna", "relaks", "wieczór", "stres", "sen", "rozciąganie"],
    "Dynamiczna / Vinyasa": ["vinyasa", "power", "flow", "energia", "dynamiczna", "pot"],
    "Poranna": ["dzień dobry", "poranna", "poranek", "rozruch", "pobudzenie"],
    "Dla początkujących": ["początkujących", "podstawy", "łagodna", "prosta"],
}

YOGA_FOCUS = {
    "Kręgosłup": ["kręgosłup", "plecy", "zdrowy kręgosłup", "odcinek"],
    "Biodra": ["biodra", "bioder", "miednica"],
    "Brzuch / Core": ["brzuch", "core", "mięśnie brzucha", "centrum"],
    "Całe ciało": ["całe ciało", "full body", "ogólno"],
}

MOBILITY_TYPE = {
    "Stretching": ["rozciąganie", "stretching", "stretch", "elastyczność"],
    "Mobility": ["mobilność", "mobility", "zakresy", "ruchomość"],
    "Rolowanie": ["rolowanie", "roller", "rozluźnianie", "automasaż", "piłeczka"],
    "Wzmacnianie": ["wzmacnianie", "siła", "stabilizacja", "aktywacja"],
}

MOBILITY_BODY = {
    "Biodra": ["biodra", "bioder", "miednica", "pośladki", "otwieranie bioder"],
    "Barki & Szyja": ["barki", "barków", "ramiona", "szyja", "kark", "klatka"],
    "Kręgosłup": ["kręgosłup", "plecy", "lędźwi", "grzbiet", "kręgosłupa"],
    "Nogi": ["nogi", "nóg", "uda", "staw skokowy", "stopy", "łydki", "kolana"],
    "Nadgarstki": ["nadgarstki", "dłonie", "przedramiona"],
    "Całe ciało": ["całe ciało", "full body", "ogólne"],
}

# Movement taxonomy — EN+PL hybrydowe (te kanały publikują po angielsku).
MOVEMENT_TYPE = {
    "Mobility": ["mobility", "mobilność", "joint", "range of motion", "rom"],
    "Stretching": ["stretching", "stretch", "flexibility", "rozciąganie", "elastyczność", "splits"],
    "(P)rehab": ["prehab", "rehab", "rehabilitation", "injury", "pain", "korekcja", "physical therapy", "physio"],
    "Strength": ["strength", "strengthening", "wzmacnianie", "stability", "stabilizacja", "control"],
    "Movement / Flow": ["flow", "movement", "animal", "locomotion", "primal", "creative"],
}

MOVEMENT_BODY = {
    "Biodra / Hips": ["hip", "hips", "biodra", "bioder", "miednica", "pelvis", "glute"],
    "Kolana / Knees": ["knee", "knees", "kolana", "kolan", "patella"],
    "Plecy / Back": ["back", "spine", "kręgosłup", "plecy", "lower back", "thoracic", "lumbar"],
    "Barki / Shoulders": ["shoulder", "shoulders", "barki", "scapula", "rotator cuff", "klatka", "chest"],
    "Szyja / Neck": ["neck", "szyja", "kark", "cervical"],
    "Kostki / Ankles": ["ankle", "ankles", "kostka", "kostki", "foot", "feet", "stopy", "stopa", "calf"],
    "Nadgarstki / Wrists": ["wrist", "wrists", "nadgarstki", "elbow", "łokieć"],
    "Całe ciało / Full body": ["full body", "całe ciało", "total body", "head to toe", "everything"],
}


def match_tags(text: str, taxonomy: dict[str, list[str]]) -> list[str]:
    text = text.lower()
    return [cat for cat, keywords in taxonomy.items() if any(k in text for k in keywords)]


def channel_iter(channels: dict):
    """Yields (name, channel_id, max_videos) — supports value=ID or (ID, limit)."""
    for name, val in channels.items():
        if isinstance(val, tuple):
            yield name, val[0], val[1]
        else:
            yield name, val, None
