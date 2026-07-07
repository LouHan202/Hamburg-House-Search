"""
Scraper for VON POLL IMMOBILIEN, Hamburg-Alstertal office
(von-poll.com/de/immobilienmakler/hamburg-alstertal).

Unlike the other franchise concern (Dahler, not yet checked), this page
turned out to be simple: it lists ~50 current listings on a single page
with no pagination needed, each as one link whose text contains
everything -- PLZ, Ort, title, Wohnfläche, Grundstück (if any), Zimmer,
and price, e.g.:

    "22397 Hamburg Zeitlos schöner Architekten-Bungalow mit Charakter
     und Gartenidylle Wohnflächeca. 167 m² • Grundstückca. 1102 m² •
     Zimmer5 897.000 EUR"

Some listings are rentals (Kaltmiete) rather than purchases -- these
show a suspiciously low "price" (e.g. "2.550 EUR" for a house). Since
there's no explicit Kauf/Miete label in the text, we use a simple
heuristic: any parsed price under 10,000 EUR is treated as a monthly
rent rather than a purchase price.
"""

import logging
import re

import requests
from bs4 import BeautifulSoup

from scrapers.common import build_record, parse_price, parse_area

logger = logging.getLogger(__name__)

LIST_URL = "https://www.von-poll.com/de/immobilienmakler/hamburg-alstertal"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    )
}

DETAIL_HREF_RE = re.compile(r"^https://www\.von-poll\.com/de/expose/hamburg-alstertal/\d+$")
WOHNFLAECHE_RE = re.compile(r"Wohnfl[aä]checa\.?\s*([\d.,]+)\s*m")
GRUNDSTUECK_RE = re.compile(r"Grundst[uü]checa\.?\s*([\d.,]+)\s*m")
PRICE_RE = re.compile(r"([\d.,]+)\s*EUR")
RENT_THRESHOLD = 10_000  # prices below this are treated as monthly rent, not purchase price


def _parse_listing(anchor) -> dict:
    text = anchor.get_text(" ", strip=True)
    href = anchor["href"]
    listing_id = href.rstrip("/").rsplit("/", 1)[-1]

    wohnflaeche_m = WOHNFLAECHE_RE.search(text)
    grundstueck_m = GRUNDSTUECK_RE.search(text)
    price_m = PRICE_RE.search(text)

    # Location + title: everything before the "Wohnfläche"/"Grundstück" marker
    cutoff = len(text)
    for m in (wohnflaeche_m, grundstueck_m):
        if m:
            cutoff = min(cutoff, m.start())
    ort_and_title = text[:cutoff].strip()

    price = parse_price(price_m.group(0)) if price_m else None
    status = "Kauf"
    if price is not None and price < RENT_THRESHOLD:
        status = "Miete"

    return build_record(
        source="vonpoll",
        listing_id=listing_id,
        title=ort_and_title,
        url=href,
        ort=ort_and_title,      # substring-matched by area_matches(), no need to split out cleanly
        objektart=ort_and_title,  # same for type_matches()
        price=price,
        living_area=parse_area(wohnflaeche_m.group(0)) if wohnflaeche_m else None,
        plot_area=parse_area(grundstueck_m.group(0)) if grundstueck_m else None,
        status=status,
    )


def fetch_listings() -> list:
    response = requests.get(LIST_URL, headers=HEADERS, timeout=20)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    anchors = soup.find_all("a", href=DETAIL_HREF_RE)
    seen_hrefs = set()
    records = []
    for a in anchors:
        href = a["href"]
        if href in seen_hrefs:
            continue
        seen_hrefs.add(href)
        try:
            records.append(_parse_listing(a))
        except Exception:
            logger.warning("Failed to parse a Von Poll listing, skipping.")

    return records
