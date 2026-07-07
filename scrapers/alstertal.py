"""
Scraper for ALSTERTAL IMMOBILIEN (alstertal-immo.de).

Unlike Bayer and Hintz & Hintz, this site shows all current listings on a
single page (https://www.alstertal-immo.de/immobilienangebote/) with no
pagination and, notably, no individual detail link per listing -- so there's
no stable per-listing URL or ID to key on. Listings are identified by a
hash of their title + location instead.

Layout observed (as rendered text, top to bottom, repeating):
    <title heading>
    <PLZ + Ort line, e.g. "22397 Hamburg-Duvenstedt">
    <specs line, e.g. "Wohnfläche ca. 175 m²Grundstück ca. 647 m²">
    <price heading, e.g. "845.000 €">           <- absent if sold/pending
Sold/pending listings show "Bereits" / "Verkauft!" markers instead of a
price heading.
"""

import hashlib
import logging
import re

import requests
from bs4 import BeautifulSoup

from scrapers.common import build_record, parse_price, parse_area

logger = logging.getLogger(__name__)

BASE = "https://www.alstertal-immo.de"
LIST_URL = f"{BASE}/immobilienangebote/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    )
}

LOCATION_RE = re.compile(r"^\d{5}\s+\S")
PRICE_RE = re.compile(r"[\d.,]+\s*€")
SOLD_MARKERS = ("bereits", "verkauft")


def _make_id(title: str, ort: str) -> str:
    return hashlib.sha1(f"{title}|{ort}".encode("utf-8")).hexdigest()[:12]


def fetch_listings() -> list:
    response = requests.get(LIST_URL, headers=HEADERS, timeout=20)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    lines = [
        line.strip()
        for line in soup.get_text(separator="\n").split("\n")
        if line.strip()
    ]

    records = []
    pending_status = None
    i = 0
    while i < len(lines):
        line = lines[i]

        if any(marker in line.lower() for marker in SOLD_MARKERS):
            pending_status = "sold"
            i += 1
            continue

        # A location line signals the *previous* line was the title.
        if LOCATION_RE.match(line) and i > 0:
            title = lines[i - 1]
            ort = line
            specs = lines[i + 1] if i + 1 < len(lines) else ""

            price = None
            consumed_price_line = False
            if i + 2 < len(lines) and PRICE_RE.search(lines[i + 2]):
                price = parse_price(lines[i + 2])
                consumed_price_line = True

            living_area_m = re.search(r"Wohnfläche[^\d]*([\d.,]+)\s*m", specs)
            plot_area_m = re.search(r"Grundst[^\d]*([\d.,]+)\s*m", specs)

            status = pending_status or ("Kauf" if price else "pending")
            pending_status = None

            try:
                records.append(build_record(
                    source="alstertal",
                    listing_id=_make_id(title, ort),
                    title=title,
                    url=LIST_URL,  # no individual listing pages on this site
                    ort=ort,
                    objektart=None,
                    price=price,
                    living_area=parse_area(living_area_m.group(0)) if living_area_m else None,
                    plot_area=parse_area(plot_area_m.group(0)) if plot_area_m else None,
                    status=status,
                ))
            except Exception:
                logger.warning("Failed to parse an Alstertal Immobilien listing, skipping.")

            i += 3 if consumed_price_line else 2
            continue

        i += 1

    return records
