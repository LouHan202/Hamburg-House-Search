"""
Scraper for Diplom-Kaufmann Hans-Peter Bayer GmbH (bayer-hamburg.de).

Pagination here isn't URL-based at all -- confirmed via browser DevTools
that clicking a page number fires a POST request to the same URL
(https://bayer-hamburg.de/angebote), with the target page number and a
couple of TYPO3 Extbase "trust" tokens (__referrer, __trustedProperties)
sent as form data. Those tokens are generated fresh on every page load
and sit in hidden <input> fields on the page -- so the approach is:

    1. GET the page once, scrape those hidden field values straight out
       of the HTML (they're not secret, just anti-tampering tokens)
    2. POST them back for page=2, page=3, etc., reusing the same tokens
       from that single GET

No login or persistent session needed. If Bayer's site ever changes
this form structure, the hidden fields won't be found and this falls
back to page-1-only, same as before.
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
    ),
    "Origin": BASE,
    "Referer": LIST_URL,
}

# Hidden form field names (as seen in the real POST payload) that need to
# be echoed back unchanged for the pagination request to be accepted.
TOKEN_FIELDS = [
    "tx_openimmo_immobilie[__referrer][@extension]",
    "tx_openimmo_immobilie[__referrer][@controller]",
    "tx_openimmo_immobilie[__referrer][@action]",
    "tx_openimmo_immobilie[__referrer][arguments]",
    "tx_openimmo_immobilie[__referrer][@request]",
    "tx_openimmo_immobilie[__trustedProperties]",
]


def _fetch_get(url: str) -> BeautifulSoup:
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def _extract_tokens(soup: BeautifulSoup) -> dict:
    tokens = {}
    for field_name in TOKEN_FIELDS:
        input_tag = soup.find("input", attrs={"name": field_name})
        if input_tag and input_tag.get("value") is not None:
            tokens[field_name] = input_tag["value"]
    return tokens


def _parse_listing_block(anchor) -> dict:
    container = anchor
    block_text = ""
    for _ in range(6):
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
        ort=title,
        objektart=title,  # site has no separate type field; filter on title text instead
        price=parse_price(kaufpreis_raw) or parse_price(miete_raw),
        living_area=parse_area(wohnflaeche_raw),
        plot_area=parse_area(grundstueck_raw),
        status="Miete" if miete_raw and not kaufpreis_raw else "Kauf",
    )


def _extract_records(soup: BeautifulSoup) -> list:
    anchors = soup.find_all("a", href=re.compile(r"^/angebot/"))
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


def fetch_listings(max_pages: int = 8) -> list:
    soup = _fetch_get(LIST_URL)
    all_records = _extract_records(soup)
    seen_ids = {r["id"] for r in all_records}

    tokens = _extract_tokens(soup)
    if len(tokens) < len(TOKEN_FIELDS):
        logger.warning(
            "Bayer's pagination form fields have changed or weren't found -- "
            "only page 1 scraped. See scrapers/bayer.py TOKEN_FIELDS."
        )
        return all_records

    for page in range(2, max_pages + 1):
        form_data = dict(tokens)
        form_data["tx_openimmo_immobilie[search]"] = "paginate"
        form_data["tx_openimmo_immobilie[page]"] = str(page)
        form_data["tx_openimmo_immobilie[objektart]"] = ""
        form_data["tx_openimmo_immobilie[vermarktungsart]"] = ""
        form_data["tx_openimmo_immobilie[ort]"] = ""

        try:
            response = requests.post(LIST_URL, headers=HEADERS, data=form_data, timeout=20)
            response.raise_for_status()
        except requests.RequestException:
            logger.warning(f"Bayer pagination POST failed on page {page}, stopping.")
            break

        page_soup = BeautifulSoup(response.text, "html.parser")
        records = _extract_records(page_soup)
        new_records = [r for r in records if r["id"] not in seen_ids]
        if not new_records:
            break  # reached the last page

        all_records.extend(new_records)
        seen_ids |= {r["id"] for r in new_records}

    return all_records
