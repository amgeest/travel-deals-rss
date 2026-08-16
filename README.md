# Travel Deals RSS Filter

This project combines several travel-deal sources into one RSS feed and keeps only items containing at least one configured keyword.

Default keywords:

- Amsterdam
- Rotterdam
- error fare

## Sources

1. https://www.fly4free.com/flight-deals/netherlands/feed/
2. https://travelunlimited.be/feed/
3. https://www.flynous.com/cheap-flights/benelux/
4. https://www.dot-global.org/articles/budget-travel-tips-and-destinations.html?psystem=PW&domain=tip.tips&oref=https%3A%2F%2Ftip.tips%2Fftrss&trafficTarget=reseller
5. https://www.vakantiepiraten.nl/feed
6. https://yelmair.com/feed

The Flynous URL and the dot-global URL are web pages rather than conventional RSS feeds, so the script can scrape matching article links from those pages. The RSS sources are read normally.

## What it does

- fetches the configured sources
- searches title, summary and content for the keywords
- matches case-insensitively
- combines results into `docs/feed.xml`
- removes duplicates by URL
- remembers previously seen URLs in `state.json`
- runs automatically via GitHub Actions

## GitHub Pages setup

1. Create a new GitHub repository.
2. Upload all files from this project.
3. In **Settings → Pages**, choose **GitHub Actions** as the source.
4. The workflow will build `docs/feed.xml`.
5. The feed will normally be available at:

   `https://YOUR-USERNAME.github.io/YOUR-REPOSITORY/feed.xml`

The workflow is scheduled every 10 minutes. GitHub may delay scheduled jobs occasionally.

## Local test

```bash
pip install -r requirements.txt
python travel_feed.py
```

Then inspect `docs/feed.xml`.

## Changing keywords

Edit `KEYWORDS` in `travel_feed.py`.

## Important

The sources are third-party websites. If a source changes its RSS structure or HTML layout, its parser may need updating. The script deliberately fails gracefully for an individual source so that one broken source does not stop the other sources from being processed.
