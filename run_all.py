"""
Main entry point. Runs every site scraper in scrapers/, filters results
down to your target Stadtteile and property types (see
scrapers/common.py), and merges everything into data/listings.json.

Run manually:
    pip install -r requirements.txt
    python run_all.py

Scheduled daily via .github/workflows/scrape.yml
"""

import logging

from scrapers import bayer, hintzhintz, alstertal, stark, wentzel
# vonpoll disabled: 403 Forbidden from GitHub Actions' cloud IPs (anti-bot).
# fruendt disabled: two different structural parsing approaches both
# returned zero listings -- likely JavaScript-rendered content that a
# plain requests fetch can't see. Would need a headless browser to revisit.
# from scrapers import vonpoll, fruendt
from scrapers.common import (
    area_matches,
    type_matches,
    load_existing,
    merge_records,
    save,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

SOURCES = {
    "bayer": bayer.fetch_listings,
    "hintzhintz": hintzhintz.fetch_listings,
    "alstertal": alstertal.fetch_listings,
    "stark": stark.fetch_listings,
    # "fruendt": fruendt.fetch_listings,  # disabled -- see comment above
    # "vonpoll": vonpoll.fetch_listings,  # disabled -- see comment above
}


def main():
    existing = load_existing()
    all_new_records = []

    for name, fetch_fn in SOURCES.items():
        logger.info(f"Scraping {name}...")
        try:
            records = fetch_fn()
        except Exception:
            logger.exception(f"{name} scraper failed, skipping it this run.")
            continue

        before = len(records)
        matched = [
            r for r in records
            if area_matches(r["ort"]) and type_matches(r["objektart"])
        ]
        logger.info(
            f"{name}: {before} listings found, {len(matched)} match your area/type filters."
        )
        if before > 0 and len(matched) == 0:
            sample = records[:3]
            for r in sample:
                logger.info(f"  (unmatched example -- ort: {r['ort'][:80]!r})")
        records = matched
        all_new_records.extend(records)

    new_count = merge_records(existing, all_new_records)
    save(existing)

    logger.info(f"Done. {new_count} brand-new listings. {len(existing)} total tracked.")


if __name__ == "__main__":
    main()
