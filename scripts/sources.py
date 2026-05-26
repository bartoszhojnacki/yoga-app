"""Konfiguracja źródeł danych i taksonomii tagów.

Zmień YOGA_CHANNELS / MOBILITY_CHANNELS żeby dodać/usunąć kanały YouTube.
Słowniki keywords używane są do auto-tagowania filmów mobility oraz
do enrichment wyników AI dla jogi (curator).
"""

YOGA_CHANNELS = {
    "Małgorzata Mostowska": "UCITlHzj4MUzRNM17pdWUWeQ",
    "Yoga Home": "UCUVNvkkzMrT4qMhlql2t4iQ",
}

MOBILITY_CHANNELS = {
    "Malva Stretching": "UCIJA9AD3fxbDNwARNBww5mg",
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


def match_tags(text: str, taxonomy: dict[str, list[str]]) -> list[str]:
    text = text.lower()
    return [cat for cat, keywords in taxonomy.items() if any(k in text for k in keywords)]
