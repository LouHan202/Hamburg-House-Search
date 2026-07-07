"""
Scraper for Hintz & Hintz Immobilien GmbH (hintzundhintz.de), the
Alstertal/Walddörfer agency.

WordPress site using the "Powermakler" real estate theme -- standard
pagination at /immobilien/page/2, /immobilien/page/3, etc. (confirmed
by inspecting the site), no anti-bot measures. Each listing card shows
Ort, Objektart, Zimmer, Kaufpreis or Miete, an internal ID, and a
Details link.

Listings prefixed "Gut verkauft" / "Gut vermietet" are already
under contract -- we keep them in the dataset (status="sold_rented")
but they're filtered out of the "currently available" view in the
dashboard.
"""

import logging
import re

import requests
from bs4 import BeautifulSoup

from scrapers.common import build_record, parse_price, parse_area

logger = logging.getLogger(__name__)

BASE = "https://hintzundhintz.de"
LIST_URL = f"{BASE}/immobilien"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    )
}

DETAIL_HREF_RE = re.compile(r"^https://hintzundhintz\.de/immobilien/(?!page/)[^/?]+/?$")


def _fetch(url: str) -> BeautifulSoup:
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def _parse_listing_block(anchor) -> dict:
    container = anchor
    block_text = ""
    for _ in range(6):
        container = container.parent
        if container is None:
            break
        block_text = container.get_text(separator="\n", strip=True)
        if "ID:" in block_text and ("Ort" in block_text or "Objektart" in block_text):
            break

    def field(label):
        m = re.search(rf"{label}\s*\n?\s*([^\n]+)", block_text)
        return m.group(1).strip() if m else None

    title_tag = container.find(["h2", "h3"]) if container else None
    raw_title = title_tag.get_text(strip=True) if title_tag else anchor.get_text(strip=True)

    status = None
    title = raw_title
    for marker in ["–Gut verkauft–", "–Gut vermietet–", "Gut verkauft", "Gut vermietet"]:
        if raw_title.startswith(marker):
            status = "sold_rented"
            title = raw_title[len(marker):].strip()
            break

    ort = field("Ort")
    objektart = field("Objektart")
    kaufpreis_raw = field("Kaufpreis")
    miete_raw = field("Miete")
    listing_id_raw = field("ID:")

    if status is None:
        status = "Miete" if miete_raw and not kaufpreis_raw else "Kauf"

    return build_record(
        source="hintzhintz",
        listing_id=listing_id_raw or anchor["href"],
        title=title,
        url=anchor["href"],
        ort=ort,
        objektart=objektart,
        price=parse_price(kaufpreis_raw) or parse_price(miete_raw),
        living_area=parse_area(field("Wohnfläche")),
        plot_area=parse_area(field("Grundstücksfläche")),
        status=status,
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
            logger.warning("Failed to parse a Hintz & Hintz listing block, skipping.")
    return records


def fetch_listings(max_pages: int = 10) -> list:
    all_records = []
    seen_ids = set()

    for page in range(1, max_pages + 1):
        url = LIST_URL if page == 1 else f"{LIST_URL}/page/{page}"
        try:
            soup = _fetch(url)
        except requests.RequestException:
            break

        records = _extract_records(soup)
        if not records:
            break

        new_records = [r for r in records if r["id"] not in seen_ids]
        if not new_records:
            break  # last page reached, WordPress just re-showed page 1

        all_records.extend(new_records)
        seen_ids |= {r["id"] for r in new_records}

    return all_records
