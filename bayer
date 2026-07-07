"""
Scraper for Diplom-Kaufmann Hans-Peter Bayer GmbH (bayer-hamburg.de),
the Alstertal-based agency.

The site is TYPO3 CMS with structured "Label: Value" fields per listing
(Objektnr, Baujahr, Kaufpreis, Wohnfläche, Grundstücksfläche) but no
documented pagination API. Since the exact pagination query parameter
isn't publicly documented, this scraper auto-detects it at runtime: it
tries a handful of common TYPO3 pagination formats and keeps whichever
one actually returns a different set of listings on "page 2".

If auto-detection fails, it falls back to scraping just the first page
and logs a warning -- with only ~13 total listings on this site split
across ~5 pages of 3, that's a real (if partial) coverage gap. See
README.md for how to fix this by hand in 30 seconds if it comes up.
"""

import logging
import re

import requests
from bs4 import BeautifulSoup

from scrapers.common import build_record, parse_price, parse_area

logger = logging.getLogger(__name__)

BASE = "https://bayer-hamburg.de"
LIST_URL = f"{BASE}/angebote"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    )
}

# Candidate pagination query-string templates to try, in order.
# {page} gets replaced with 2, 3, 4, ...
PAGINATION_CANDIDATES = [
    "?tx_openimmo_list%5B%40widget_0%5D%5BcurrentPage%5D={page}",
    "?tx_openimmo_pi1%5Bpage%5D={page}",
    "?tx_openimmo_list%5Bpage%5D={page}",
    "?page={page}",
]


def _fetch(url: str) -> BeautifulSoup:
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def _parse_listing_block(anchor) -> dict:
    """Given a <a href="/angebot/..."> details anchor, walk up to find the
    surrounding listing container and pull out the labeled fields."""
    container = anchor
    block_text = ""
    for _ in range(6):  # walk up a few parent levels looking for a rich block
        container = container.parent
        if container is None:
            break
        block_text = container.get_text(separator="\n", strip=True)
        if "Kaufpreis" in block_text or "Baujahr" in block_text or "Nettokaltmiete" in block_text:
            break

    title_tag = container.find(["h2", "h3"]) if container else None
    title = title_tag.get_text(strip=True) if title_tag else anchor.get_text(strip=True)

    def field(label):
        m = re.search(rf"{label}:\s*([^\n]+)", block_text)
        return m.group(1).strip() if m else None

    objektnr = field("Objektnr\\. extern")
    kaufpreis_raw = field("Kaufpreis")
    miete_raw = field("Nettokaltmiete")
    wohnflaeche_raw = field("Wohnfläche")
    grundstueck_raw = field("Grundstücksfläche")

    return build_record(
        source="bayer",
        listing_id=objektnr or anchor["href"],
        title=title,
        url=BASE + anchor["href"] if anchor["href"].startswith("/") else anchor["href"],
        ort=title,  # this site doesn't show a separate "Ort" field in the list view;
                    # the Stadtteil is embedded in the title text instead
        objektart=None,  # not exposed separately in the list view either
        price=parse_price(kaufpreis_raw) or parse_price(miete_raw),
        living_area=parse_area(wohnflaeche_raw),
        plot_area=parse_area(grundstueck_raw),
        status="Miete" if miete_raw and not kaufpreis_raw else "Kauf",
    )


def _extract_records(soup: BeautifulSoup) -> list:
    anchors = soup.find_all("a", href=re.compile(r"^/angebot/"))
    # de-duplicate: each listing usually has 2 anchors (image + "Details")
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
            logger.warning("Failed to parse a Bayer listing block, skipping.")
    return records


def _detect_pagination_template(page1_ids: set):
    for template in PAGINATION_CANDIDATES:
        url = LIST_URL + template.format(page=2)
        try:
            soup = _fetch(url)
        except requests.RequestException:
            continue
        records = _extract_records(soup)
        ids = {r["id"] for r in records}
        if ids and ids != page1_ids:
            logger.info(f"Detected working pagination template: {template}")
            return template
    logger.warning(
        "Could not auto-detect Bayer's pagination scheme -- only page 1 "
        "will be scraped. See README.md to set this by hand."
    )
    return None


def fetch_listings(max_pages: int = 6) -> list:
    soup = _fetch(LIST_URL)
    all_records = _extract_records(soup)
    page1_ids = {r["id"] for r in all_records}

    template = _detect_pagination_template(page1_ids)
    if template:
        seen_ids = set(page1_ids)
        for page in range(2, max_pages + 1):
            url = LIST_URL + template.format(page=page)
            try:
                soup = _fetch(url)
            except requests.RequestException:
                break
            records = _extract_records(soup)
            new_ids = {r["id"] for r in records} - seen_ids
            if not new_ids:
                break  # reached the last page (results repeat)
            all_records.extend(r for r in records if r["id"] in new_ids)
            seen_ids |= new_ids

    return all_records
