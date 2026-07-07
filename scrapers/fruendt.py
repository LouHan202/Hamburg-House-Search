"""
Scraper for FRÜNDT IMMOBILIEN GMBH (fruendt.de), Alstertal/Walddörfer
specialists with 60+ years in the area.

Their listings are actually hosted on a separate platform: onOffice
"Smart Site" (smartsite2.myonoffice.de/kunden/fruendt/57/kaufen.xhtml).
This is a real estate CRM product used by many small/independent German
agencies -- worth knowing, since the same parsing approach here could
likely be reused for any other agency running onOffice Smart Site (just
swap the customer slug + numeric ID in the URL).

Listing data is rendered as genuine HTML <table> elements with clean
"Label / Value" rows (PLZ, Ort, Kaufpreis, Wohnfläche, Grundstücksgröße,
etc.) -- the most reliable structure of any source scraped so far, since
we can parse real <tr>/<td> pairs instead of guessing at text patterns.

Caveat: only confirmed against a single fetched sample showing one
listing. It's unclear from that sample alone whether the live page
normally lists several properties at once or one at a time -- if the
real page shows more, this parser should still pick all of them up
since it scans every matching <table> on the page, but this hasn't
been verified against a multi-listing page.
"""

import logging

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


def _table_to_dict(table) -> dict:
    """onOffice renders these as rows of alternating label/value cells,
    sometimes two label/value pairs per row (a 4-cell row)."""
    data = {}
    for tr in table.find_all("tr"):
        cells = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
        for i in range(0, len(cells) - 1, 2):
            label, value = cells[i], cells[i + 1]
            if label:
                data[label] = value
    return data


def fetch_listings() -> list:
    response = requests.get(LIST_URL, headers=HEADERS, timeout=20)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    records = []
    for table in soup.find_all("table"):
        fields = _table_to_dict(table)
        if "Kaufpreis" not in fields and "PLZ" not in fields:
            continue  # not one of the "Auf einen Blick" data tables

        title_tag = table.find_previous(["h1", "h2"])
        title = title_tag.get_text(strip=True) if title_tag else fields.get("ImmoNr", "unknown")

        # Check nearby text for a reservation/sold marker (appears in the
        # "Ausstattung" prose section above the table, e.g. "***RESERVIERT***")
        preceding_text = ""
        node = table.find_previous(["h1"])
        if node:
            preceding_text = node.find_next(string=True) or ""
            preceding_text = table.find_all_previous(limit=40)
            preceding_text = " ".join(
                el.get_text(" ", strip=True) for el in preceding_text
                if hasattr(el, "get_text")
            )
        status = "reserved" if "RESERVIERT" in preceding_text.upper() else "Kauf"

        ort = " ".join(filter(None, [
            fields.get("PLZ"), fields.get("Ort"), fields.get("Stadtteile / Orte")
        ]))

        try:
            records.append(build_record(
                source="fruendt",
                listing_id=fields.get("ImmoNr", title),
                title=title,
                url=LIST_URL,  # individual listings are query-param based;
                                # the base URL is the closest stable link we have
                ort=ort,
                objektart=title,
                price=parse_price(fields.get("Kaufpreis")),
                living_area=parse_area(fields.get("Wohnfläche")),
                plot_area=parse_area(fields.get("Grundstücksgröße")),
                status=status,
            ))
        except Exception:
            logger.warning("Failed to parse a Fründt Immobilien listing, skipping.")

    return records
