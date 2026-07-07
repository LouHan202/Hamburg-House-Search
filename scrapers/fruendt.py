"""
Scraper for FRÜNDT IMMOBILIEN GMBH (fruendt.de), Alstertal/Walddörfer
specialists with 60+ years in the area.

Their listings are hosted on a separate platform: onOffice "Smart Site"
(smartsite2.myonoffice.de/kunden/fruendt/57/kaufen.xhtml) -- a real estate
CRM product used by many small/independent German agencies.

First attempt at this parser assumed the "Auf einen Blick" data (PLZ,
Ort, Kaufpreis, Wohnfläche, Grundstücksgröße) was rendered as real HTML
<table> elements -- that returned zero results on the live site, so the
assumption was wrong (the page-preview tool used to inspect this site
converts many div-based grid layouts into markdown table syntax
regardless of the underlying HTML, which is misleading). This version
instead scans the plain text near each listing heading for the same
labels, the same approach used for Bayer and Hintz & Hintz.
"""

import logging
import re

import requests
from bs4 import BeautifulSoup

from scrapers.common import build_record, parse_price, parse_area

logger = logging.getLogger(__name__)

LIST_URL = "https://smartsite2.myonoffice.de/kunden/fruendt/57/kaufen.xhtml"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    )
}


def fetch_listings() -> list:
    response = requests.get(LIST_URL, headers=HEADERS, timeout=20)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    headings = soup.find_all(["h1", "h2", "h3"])
    records = []

    for idx, heading in enumerate(headings):
        title = heading.get_text(strip=True)
        if not title:
            continue

        # Grab all text between this heading and the next one as this
        # listing's block.
        block_parts = []
        for sibling in heading.find_all_next():
            if sibling in headings[idx + 1:idx + 2]:
                break
            block_parts.append(sibling.get_text(" ", strip=True))
        block_text = " ".join(block_parts)

        if "Kaufpreis" not in block_text and "PLZ" not in block_text:
            continue  # not a listing heading (could be a nav/footer heading)

        def field(label):
            m = re.search(rf"{label}\s*:?\s*([^\s][^A-ZÄÖÜ]{{0,60}}?)(?=\s[A-ZÄÖÜ][a-zäöü]|$)", block_text)
            return m.group(1).strip() if m else None

        plz_m = re.search(r"\b(\d{5})\b", block_text)
        ort_m = re.search(r"Ort\s*:?\s*([A-ZÄÖÜ][\w\-. ]{2,40})", block_text)
        kaufpreis_m = re.search(r"Kaufpreis\s*:?\s*([\d.,]+)\s*€?", block_text)
        wohnflaeche_m = re.search(r"Wohnfl[aä]che\s*:?\s*([\d.,]+)\s*m", block_text)
        grundstueck_m = re.search(r"Grundst[uü]cksgr[oö]{1,2}e\s*:?\s*([\d.,]+)\s*m", block_text)
        immonr_m = re.search(r"ImmoNr\.?\s*:?\s*([\w\-]+)", block_text)

        is_reserved = "RESERVIERT" in block_text.upper()
        ort = " ".join(filter(None, [
            plz_m.group(1) if plz_m else None,
            ort_m.group(1).strip() if ort_m else None,
        ])) or title

        try:
            records.append(build_record(
                source="fruendt",
                listing_id=immonr_m.group(1) if immonr_m else title,
                title=title,
                url=LIST_URL,
                ort=ort,
                objektart=title,
                price=parse_price(kaufpreis_m.group(0)) if kaufpreis_m else None,
                living_area=parse_area(wohnflaeche_m.group(0)) if wohnflaeche_m else None,
                plot_area=parse_area(grundstueck_m.group(0)) if grundstueck_m else None,
                status="reserved" if is_reserved else "Kauf",
            ))
        except Exception:
            logger.warning("Failed to parse a Fründt Immobilien listing, skipping.")

    return records
