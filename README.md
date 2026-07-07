# Hamburg-House-Search
# Hamburg House Tracker

Daily scrape of two local Hamburg real estate agencies -- Bayer Immobilien
(bayer-hamburg.de) and Hintz & Hintz (hintzundhintz.de) -- covering the
Alstertal, Walddörfer, Langenhorn, and Fuhlsbüttel. Tracked over time in
`data/listings.json`, deduplicated, with price/m² calculated per listing.

## Why these two sites

Both are small independent agencies with their own listing pages --
no ImmoScout24 anti-bot protection, no rate limiting encountered during
testing. This is exactly the kind of "smaller local site nobody else is
watching closely" source that tends to surface undervalued listings.

## Setup (one-time, ~10 minutes)

1. **Create a new GitHub repo** (private is fine).

2. **Add these files**, keeping the folder structure:
   ```
   run_all.py
   requirements.txt
   scrapers/__init__.py
   scrapers/common.py
   scrapers/bayer.py
   scrapers/hintzhintz.py
   .github/workflows/scrape.yml
   ```

3. **Push to GitHub.** No API keys needed.

4. **Run it once manually**: repo → Actions tab → "Scrape Hamburg listings"
   → Run workflow. Check the log output and `data/listings.json` afterward.

## Known limitation: Bayer's pagination

Bayer's site (bayer-hamburg.de) has ~13 listings split across ~5 pages,
but doesn't publicly document its pagination URL format. The scraper
auto-detects it by trying a few common patterns -- if none of them work,
it'll log a warning and only scrape page 1 (3 of the 13 listings).

**If you see that warning in the Actions log**, here's the 30-second fix:
1. Open https://bayer-hamburg.de/angebote in your browser
2. Click "2" in the pagination at the bottom
3. Copy the full URL from your address bar
4. Send it to me (or add it as a new entry in `PAGINATION_CANDIDATES` in
   `scrapers/bayer.py`) and the scraper will pick it up correctly

Hintz & Hintz doesn't have this problem -- its pagination
(`/immobilien/page/2`, `/page/3`, ...) is standard WordPress and confirmed
working.

## Your search area

Edit `TARGET_AREAS` in `scrapers/common.py` to adjust. Currently set to:

Poppenbüttel, Wellingsbüttel, Sasel, Volksdorf, Duvenstedt,
Wohldorf-Ohlstedt, Bergstedt, Lemsahl-Mellingstedt, Langenhorn,
Fuhlsbüttel, Rahlstedt, Farmsen-Berne

`TARGET_TYPES` controls which Objektart values are kept (currently:
Haus, Einfamilienhaus, Zweifamilienhaus, Mehrfamilienhaus, Grundstück).

## A note on field-extraction accuracy

Both scrapers parse listing data using text-pattern matching (looking for
"Kaufpreis: ...", "Wohnfläche: ..." etc. in the rendered page text) rather
than exact HTML class names, since those weren't available to verify
directly while building this. This should be robust to most layout
variations, but if you notice missing prices or areas after the first
run, flag it and the parsing patterns in `scrapers/bayer.py` /
`scrapers/hintzhintz.py` can be tightened.

## A note on scraping etiquette

Once a day, non-commercial, personal search -- reasonable for small sites
like these. Keep it at this frequency; don't scale it up.

## Next step

Once `data/listings.json` has real data in it, that feeds directly into
the dashboard artifact (price/m² comparison, undervalued flagging) --
just share its contents and I'll build the visualization.
