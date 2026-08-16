import html
import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin

import feedparser
import requests
from bs4 import BeautifulSoup

KEYWORDS = ["Amsterdam", "Rotterdam", "error fare"]

SOURCES = [
    {
        "name": "Fly4Free Netherlands",
        "url": "https://www.fly4free.com/flight-deals/netherlands/feed/",
        "type": "rss",
    },
    {
        "name": "TravelUnlimited",
        "url": "https://travelunlimited.be/feed/",
        "type": "rss",
    },
    {
        "name": "Flynous Benelux",
        "url": "https://www.flynous.com/cheap-flights/benelux/",
        "type": "html",
    },
    {
        "name": "Dot Global",
        "url": "https://www.dot-global.org/articles/budget-travel-tips-and-destinations.html?psystem=PW&domain=tip.tips&oref=https%3A%2F%2Ftip.tips%2Fftrss&trafficTarget=reseller",
        "type": "html",
    },
    {
        "name": "VakantiePiraten",
        "url": "https://www.vakantiepiraten.nl/feed",
        "type": "rss",
    },
    {
        "name": "Yelmair",
        "url": "https://yelmair.com/feed",
        "type": "rss",
    },
]

OUT_DIR = Path("docs")
STATE_FILE = Path("state.json")
FEED_FILE = OUT_DIR / "feed.xml"
MAX_ITEMS = 100

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; TravelDealsRSS/1.0; "
        "+https://github.com/)"
    )
}


def clean_text(value):
    if not value:
        return ""
    soup = BeautifulSoup(str(value), "html.parser")
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()


def matches(item):
    haystack = " ".join(
        [
            item.get("title", ""),
            item.get("summary", ""),
            item.get("content", ""),
        ]
    ).casefold()
    return any(keyword.casefold() in haystack for keyword in KEYWORDS)


def parse_date(value):
    if not value:
        return datetime.now(timezone.utc)

    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = parsedate_to_datetime(value)
        except Exception:
            dt = None

    if dt is None:
        return datetime.now(timezone.utc)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def rss_source(source):
    response = requests.get(
        source["url"], headers=HEADERS, timeout=30
    )
    response.raise_for_status()

    parsed = feedparser.parse(response.content)
    items = []

    for entry in parsed.entries:
        title = clean_text(entry.get("title", ""))
        link = entry.get("link", "")
        summary = clean_text(
            entry.get("summary", "") or entry.get("description", "")
        )

        content_parts = []
        for content in entry.get("content", []):
            content_parts.append(clean_text(content.get("value", "")))

        published = (
            entry.get("published")
            or entry.get("updated")
            or entry.get("created")
        )

        item = {
            "title": title,
            "link": link,
            "summary": summary,
            "content": " ".join(content_parts),
            "published": parse_date(published),
            "source": source["name"],
        }

        if link and matches(item):
            items.append(item)

    return items


def html_source(source):
    response = requests.get(
        source["url"], headers=HEADERS, timeout=30
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    candidates = []

    # Prefer article elements, then fall back to links.
    blocks = soup.find_all(["article", "div", "section"])
    for block in blocks:
        link = block.find("a", href=True)
        heading = block.find(["h1", "h2", "h3", "h4"])
        if not link or not heading:
            continue

        title = clean_text(heading.get_text(" ", strip=True))
        href = urljoin(response.url, link["href"])
        summary = clean_text(block.get_text(" ", strip=True))

        if len(title) < 4:
            continue

        candidates.append(
            {
                "title": title,
                "link": href,
                "summary": summary,
                "content": summary,
                "published": datetime.now(timezone.utc),
                "source": source["name"],
            }
        )

    # Fallback: inspect headings and their nearest link.
    if not candidates:
        for heading in soup.find_all(["h1", "h2", "h3", "h4"]):
            title = clean_text(heading.get_text(" ", strip=True))
            link = heading.find("a", href=True) or heading.parent.find(
                "a", href=True
            ) if heading.parent else None
            if not link:
                continue
            href = urljoin(response.url, link["href"])
            candidates.append(
                {
                    "title": title,
                    "link": href,
                    "summary": title,
                    "content": title,
                    "published": datetime.now(timezone.utc),
                    "source": source["name"],
                }
            )

    return [item for item in candidates if item["link"] and matches(item)]


def load_state():
    if not STATE_FILE.exists():
        return {"seen": []}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"seen": []}


def save_state(seen):
    # Keep the state file reasonably small.
    STATE_FILE.write_text(
        json.dumps({"seen": list(seen)[-2000:]}, indent=2),
        encoding="utf-8",
    )


def deduplicate(items):
    result = []
    seen = set()

    for item in sorted(
        items,
        key=lambda x: x["published"],
        reverse=True,
    ):
        key = item["link"].rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        result.append(item)

    return result[:MAX_ITEMS]


def xml_escape(value):
    return html.escape(str(value), quote=True)


def make_feed(items):
    now = datetime.now(timezone.utc)
    updated = now.strftime("%a, %d %b %Y %H:%M:%S +0000")

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0">',
        "  <channel>",
        "    <title>Filtered Travel Deals — Amsterdam, Rotterdam, Error Fare</title>",
        "    <link>https://example.com/</link>",
        "    <description>Travel deals containing Amsterdam, Rotterdam or error fare.</description>",
        f"    <lastBuildDate>{updated}</lastBuildDate>",
    ]

    for item in items:
        pub = item["published"].strftime("%a, %d %b %Y %H:%M:%S +0000")
        description = item["summary"] or item["content"]
        description = description[:4000]

        parts.extend(
            [
                "    <item>",
                f"      <title>{xml_escape(item['title'])}</title>",
                f"      <link>{xml_escape(item['link'])}</link>",
                f"      <guid isPermaLink=\"true\">{xml_escape(item['link'])}</guid>",
                f"      <pubDate>{pub}</pubDate>",
                f"      <description>{xml_escape(description)}</description>",
                f"      <category>{xml_escape(item['source'])}</category>",
                "    </item>",
            ]
        )

    parts.extend(["  </channel>", "</rss>"])
    return "\n".join(parts)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    state = load_state()
    all_items = []

    for source in SOURCES:
        try:
            if source["type"] == "rss":
                found = rss_source(source)
            else:
                found = html_source(source)

            print(f"{source['name']}: {len(found)} matching item(s)")
            all_items.extend(found)
        except Exception as exc:
            print(f"WARNING: {source['name']} failed: {exc}")

    items = deduplicate(all_items)
    FEED_FILE.write_text(make_feed(items), encoding="utf-8")

    for item in items:
        state.setdefault("seen", []).append(item["link"].rstrip("/"))

    save_state(set(state["seen"]))

    print(f"Wrote {FEED_FILE} with {len(items)} item(s).")


if __name__ == "__main__":
    main()
