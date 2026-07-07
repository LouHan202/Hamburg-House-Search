"""
Scraper for Stark Immobilien (stark-immo.com), a Hamburg-wide agency
(not Alstertal-specific, but explicitly covers Fuhlsbüttel and Langenhorn
among many other Stadtteile).

WordPress/Elementor site with confirmed pagination
(stark-immo.com/kaufangebote/?page=2, ?page=3, ...). Each listing link's
text already contains the Stadtteil name (e.g. "Hamburg-Fuhlsbüttel
Vermietete 3 Zimmerwohnung..."), so rather than parsing location out
separately, we just pass that raw text through to the shared
area_matches()/type_matches() filters in scrapers/common.py, which do
substring matching and don't care about exact field boundaries.
"""

import logging
import re

import requests
from bs4 import BeautifulSoup

from scrapers.common import build_record, parse_price, parse_area

logger = logging.getLogger(__name__)

BASE = "https://stark-immo.com"
LIST_URL = f"{BASE}/kaufangebote/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    )
}

DETAIL_HREF_RE = re.compile(r"^https://stark-immo\.com/kaufangebote/[^/?]+/?$")
AREA_RE = re.compile(r"ca\.?\s*([\d.,]+)\s*m", re.IGNORECASE)
PRICE_RE = re.compile(r"€\s*([\d.,]+)")


def _fetch(url: str) -> BeautifulSoup:
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def _parse_listing_block(anchor) -> dict:
    title = anchor.get_text(strip=True).replace("MEHR ERFAHREN", "").strip()

    # Look at the text immediately following the anchor for
    # "N Zimmer | price | ca. X m²" (may appear twice due to responsive
    # mobile/desktop duplicate markup -- we just take the first match of each).
    container = anchor
    block_text = ""
    for _ in range(4):
        container = container.parent
        if container is None:
            break
        block_text = container.get_text(separator="\n", strip=True)
        if "Zimmer" in block_text or "m²" in block_text:
            break

    sold = "verkauft" in block_text.lower()
    price_match = PRICE_RE.search(block_text)
    area_match = AREA_RE.search(block_text)

    href = anchor["href"]
    listing_id = href.rstrip("/").rsplit("/", 1)[-1]

    return build_record(
        source="stark",
        listing_id=listing_id,
        title=title,
        url=href,
        ort=title,       # location is embedded in the title text; area_matches()
                         # does substring matching so this works fine as-is
        objektart=title,  # same reasoning for type_matches()
        price=None if sold else (parse_price(price_match.group(0)) if price_match else None),
        living_area=parse_area(area_match.group(0)) if area_match else None,
        plot_area=None,
        status="sold" if sold else "Kauf",
    )


def _extract_records(soup: BeautifulSoup) -> list:
    anchors = soup.find_all("a", href=DETAIL_HREF_RE)
    seen_hrefs = set()
    records = []
    for a in anchors:
        href = a["href"]
        if href in seen_hrefs:
            continue
        seen_hrefs.add(href)
        try:
            records.append(_parse_listing_block(a))
        except Exception:
            logger.warning("Failed to parse a Stark Immobilien listing, skipping.")
    return records


def fetch_listings(max_pages: int = 10) -> list:
    all_records = []
    seen_ids = set()

    for page in range(1, max_pages + 1):
        url = LIST_URL if page == 1 else f"{LIST_URL}?page={page}"
        try:
            soup = _fetch(url)
        except requests.RequestException:
            break

        records = _extract_records(soup)
        if not records:
            break

        new_records = [r for r in records if r["id"] not in seen_ids]
        if not new_records:
            break

        all_records.extend(new_records)
        seen_ids |= {r["id"] for r in new_records}

    return all_records
