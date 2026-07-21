"""
Scraper for Wentzel Dr. (wentzel-dr.de), a real estate agency with listings
across many German cities -- not Hamburg-specific. Only a small fraction of
its ~370 active listings will be in your target Stadtteile; that's expected,
and scrapers/common.py's area_matches()/type_matches() filters handle it.

WordPress/Elementor ("Frymo" plugin) site with confirmed pagination
(wentzel-dr.de/immobilien/2/, /3/, ...). Overview cards only show the city
("Hamburg"), not the Stadtteil -- so, following the same approach as
scrapers/stark.py, we pass the listing title through as both `ort` and
`objektart` and let the shared substring-matching filters do the work.
Most titles include the Stadtteil name (e.g. "... in Hamburg Poppenbüttel").

Each card (<article class="frymo-listing-item">) has:
    .frymo-listing-title a          -- title + detail URL
    .frymo-listing-meta-item-value  -- living area (m²), room count
    .frymo-listing-price span       -- price label ("Kaufpreis"/"Kaltmiete")
                                        followed by .frymo-listing-price-value
    .frymo-listing-badges           -- non-empty for sold/reserved/rented listings
No plot area (Grundstück) is shown on the overview cards; only the detail
page has it, which we skip fetching to keep this scraper light given the
site's size (~370 listings / ~31 pages).
"""

import logging

import requests
from bs4 import BeautifulSoup

from scrapers.common import build_record, parse_price, parse_area

logger = logging.getLogger(__name__)

BASE = "https://wentzel-dr.de"
LIST_URL = f"{BASE}/immobilien/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    )
}


def _fetch(url: str) -> BeautifulSoup:
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def _parse_card(article) -> dict:
    link = article.select_one(".frymo-listing-title a")
    title = link.get_text(strip=True)
    href = link["href"]
    listing_id = href.rstrip("/").rsplit("/", 1)[-1]

    area_el = article.select_one(".frymo-listing-area .frymo-listing-meta-item-value")
    living_area = parse_area(area_el.get_text(strip=True)) if area_el else None

    price_block = article.select_one(".frymo-listing-price")
    price_label = ""
    price_value = None
    if price_block:
        label_el = price_block.find("span")
        price_label = label_el.get_text(strip=True).lower() if label_el else ""
        value_el = price_block.select_one(".frymo-listing-price-value")
        if value_el:
            price_value = parse_price(value_el.get_text(strip=True))

    badge_el = article.select_one(".frymo-listing-badges")
    badge_text = badge_el.get_text(strip=True).lower() if badge_el else ""

    if "verkauft" in badge_text:
        status = "sold"
    elif "reserviert" in badge_text:
        status = "reserved"
    elif "vermietet" in badge_text:
        status = "sold_rented"
    elif "miete" in price_label:
        status = "Miete"
    else:
        status = "Kauf"

    return build_record(
        source="wentzel",
        listing_id=listing_id,
        title=title,
        url=href,
        ort=title,
        objektart=title,
        price=price_value,
        living_area=living_area,
        plot_area=None,
        status=status,
    )


def _extract_records(soup: BeautifulSoup) -> list:
    records = []
    for article in soup.select("article.frymo-listing-item"):
        try:
            records.append(_parse_card(article))
        except Exception:
            logger.warning("Failed to parse a Wentzel Dr. listing, skipping.")
    return records


def fetch_listings(max_pages: int = 40) -> list:
    all_records = []
    seen_ids = set()

    for page in range(1, max_pages + 1):
        url = LIST_URL if page == 1 else f"{BASE}/immobilien/{page}/"
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
