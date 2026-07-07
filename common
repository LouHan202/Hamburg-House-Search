"""
Shared helpers for all site-specific scrapers: the common data schema,
which Stadtteile (quarters) count as "in your search area", and the
merge/save logic that keeps data/listings.json up to date across runs.
"""

import json
import os
import re
from datetime import datetime, timezone

DATA_FILE = "data/listings.json"

# Stadtteile you're targeting: Alstertal core + Walddörfer + Langenhorn/Fuhlsbüttel.
# Matching is case-insensitive substring matching against each listing's
# "Ort" / location text, so partial names still match (e.g. "Poppenbüttel"
# matches "22399 Hamburg Poppenbüttel").
TARGET_AREAS = [
    "Poppenbüttel",
    "Wellingsbüttel",
    "Sasel",
    "Volksdorf",
    "Duvenstedt",
    "Wohldorf-Ohlstedt",
    "Bergstedt",
    "Lemsahl-Mellingstedt",
    "Langenhorn",
    "Fuhlsbüttel",
    "Rahlstedt",
    "Farmsen-Berne",
]

# Only keep these Objektart values -- adjust if you want to widen to
# Wohnung (apartments) too.
TARGET_TYPES = ["haus", "einfamilienhaus", "zweifamilienhaus",
                "mehrfamilienhaus", "grundstück", "grundstueck"]


def area_matches(location_text: str) -> bool:
    if not location_text:
        return False
    text = location_text.lower()
    return any(area.lower() in text for area in TARGET_AREAS)


def type_matches(objektart_text: str) -> bool:
    if not objektart_text:
        return True  # don't drop listings where we couldn't parse a type
    text = objektart_text.lower()
    return any(t in text for t in TARGET_TYPES)


def parse_price(text: str):
    """'755.000,00 €' -> 755000.0"""
    if not text:
        return None
    cleaned = re.sub(r"[^\d,]", "", text)
    cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_area(text: str):
    """'162,00 m²' -> 162.0"""
    if not text:
        return None
    cleaned = re.sub(r"[^\d,]", "", text)
    cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def build_record(source, listing_id, title, url, ort, objektart,
                  price, living_area, plot_area, status=None):
    price_per_sqm = None
    if price and living_area:
        price_per_sqm = round(price / living_area, 2)

    return {
        "source": source,
        "id": f"{source}:{listing_id}",
        "title": title,
        "url": url,
        "ort": ort,
        "objektart": objektart,
        "price": price,
        "living_area": living_area,
        "plot_area": plot_area,
        "price_per_sqm": price_per_sqm,
        "status": status,
    }


def load_existing() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save(data: dict) -> None:
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)


def merge_records(existing: dict, records: list) -> int:
    """Merge freshly scraped records into the existing dataset in place.
    Returns the number of genuinely new listings found."""
    now = datetime.now(timezone.utc).isoformat()
    new_count = 0

    for record in records:
        key = record["id"]
        if key in existing:
            existing[key]["price"] = record["price"]
            existing[key]["price_per_sqm"] = record["price_per_sqm"]
            existing[key]["status"] = record["status"]
            existing[key]["last_seen"] = now
        else:
            record["first_seen"] = now
            record["last_seen"] = now
            existing[key] = record
            new_count += 1

    return new_count
