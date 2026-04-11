"""RSS feed collector for SOC Planning Agent.

Fetches articles from curated feeds across 6 categories.
Returns standardised article dicts: title, url, source, published, summary, lang.
No AI processing here — raw RSS data only.
"""
import re
import socket
import urllib.request
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from typing import Optional

# ---------------------------------------------------------------------------
# Feed registry
# ---------------------------------------------------------------------------

FEEDS = {
    "chips_soc": [
        {"url": "https://www.tomshardware.com/feeds/all",        "name": "Tom's Hardware"},
        {"url": "https://www.anandtech.com/rss/",               "name": "AnandTech"},
        {"url": "https://www.eetimes.com/feed/",                "name": "EE Times"},
        {"url": "https://semiengineering.com/feed/",            "name": "SemiEngineering"},
        {"url": "https://semianalysis.com/feed/",               "name": "SemiAnalysis"},
        {"url": "https://www.qualcomm.com/news/onq/rss.xml",    "name": "Qualcomm Blog"},
        {"url": "https://www.nextplatform.com/feed/",           "name": "The Next Platform"},
    ],
    "mobile": [
        {"url": "https://9to5mac.com/feed/",                    "name": "9to5Mac"},
        {"url": "https://9to5google.com/feed/",                 "name": "9to5Google"},
        {"url": "https://feeds.macrumors.com/MacRumors-All",    "name": "MacRumors"},
        {"url": "https://www.androidauthority.com/feed/",       "name": "Android Authority"},
        {"url": "https://www.gsmarena.com/rss-news-reviews.php3","name": "GSMArena"},
        {"url": "https://daringfireball.net/feeds/main",        "name": "Daring Fireball"},
    ],
    "agentic_ai": [
        {"url": "https://techcrunch.com/category/artificial-intelligence/feed/", "name": "TechCrunch AI"},
        {"url": "https://venturebeat.com/category/ai/feed/",   "name": "VentureBeat AI"},
        {"url": "https://www.technologyreview.com/topic/artificial-intelligence/feed/", "name": "MIT Tech Review AI"},
        {"url": "https://huggingface.co/blog/feed.xml",        "name": "Hugging Face Blog"},
        {"url": "https://api.therundown.ai/rss",               "name": "Rundown AI"},
    ],
    "5g_cpe": [
        {"url": "https://www.lightreading.com/rss.xml",        "name": "Light Reading"},
        {"url": "https://www.rcrwireless.com/feed",            "name": "RCR Wireless"},
        {"url": "https://www.fiercewireless.com/rss/xml",      "name": "Fierce Wireless"},
        {"url": "https://www.3gpp.org/news-events/3gpp-news/rss", "name": "3GPP News"},
    ],
    "csp_cloud": [
        {"url": "https://aws.amazon.com/blogs/aws/feed/",      "name": "AWS Blog"},
        {"url": "https://cloud.google.com/feeds/gcp-release-notes.xml", "name": "Google Cloud"},
        {"url": "https://azure.microsoft.com/en-us/blog/feed/","name": "Azure Blog"},
        {"url": "https://thenewstack.io/feed/",                "name": "The New Stack"},
    ],
    "tech_general": [
        {"url": "https://www.wired.com/feed/rss",              "name": "Wired"},
        {"url": "https://feeds.bloomberg.com/technology/news.rss", "name": "Bloomberg Tech"},
        {"url": "https://feeds.arstechnica.com/arstechnica/index", "name": "Ars Technica"},
    ],
    "taiwan": [
        {"url": "https://www.ithome.com.tw/rss",               "name": "iThome"},
        {"url": "https://technews.tw/feed/",                   "name": "科技新報"},
        {"url": "https://technews.tw/category/finance/feed/",  "name": "科技新報財經"},
        {"url": "https://www.inside.com.tw/rss",               "name": "Inside 台灣"},
        {"url": "https://www.bnext.com.tw/rss",                "name": "數位時代"},
        {"url": "https://www.ctimes.com.tw/rss/rss-news.xml",  "name": "CTIMES"},
        {"url": "https://www.digitimes.com.tw/tech/rss/xml/xmlrss_10_60.xml",    "name": "電子時報 Digitimes-AI"},
        {"url": "https://www.digitimes.com.tw/tech/rss/xml/xmlrss_10_40.xml",    "name": "電子時報 Digitimes-semi"},
        {"url": "https://www.digitimes.com.tw/tech/rss/xml/xmlrss_30_25.xml",    "name": "電子時報 Digitimes-AI focus"},
        {"url": "https://www.digitimes.com.tw/tech/rss/xml/xmlrss_30_16.xml",    "name": "電子時報 Digitimes-IC design"},
        {"url": "https://www.digitimes.com.tw/tech/rss/xml/xmlrss_30_27.xml",    "name": "電子時報 Digitimes-Next 5G"},
        {"url": "https://www.digitimes.com.tw/tech/rss/xml/xmlrss_30_6.xml",    "name": "電子時報 Digitimes-smartphone"},
        {"url": "https://www.digitimes.com.tw/tech/rss/xml/xmlrss_30_7.xml",    "name": "電子時報 Digitimes-broadband"},
        {"url": "https://www.digitimes.com.tw/tech/rss/xml/xmlrss_10_70.xml",    "name": "電子時報 Digitimes-mobile"},
    ],
}

# 3GPP vendor feeds (weekly only)
FEEDS_3GPP = {
    "3gpp_vendors": [
        {"url": "https://www.3gpp.org/news-events/3gpp-news/rss", "name": "3GPP"},
        {"url": "https://www.ericsson.com/en/rss/press-releases", "name": "Ericsson"},
        {"url": "https://www.nokia.com/about-us/news/releases/feed/", "name": "Nokia"},
        {"url": "https://newsroom.huawei.com/en/rss",          "name": "Huawei"},
    ],
}

FETCH_TIMEOUT = 12
NS = {
    "atom":    "http://www.w3.org/2005/Atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc":      "http://purl.org/dc/elements/1.1/",
    "media":   "http://search.yahoo.com/mrss/",
}


# ---------------------------------------------------------------------------
# HTTP fetch
# ---------------------------------------------------------------------------

def _fetch(url: str) -> Optional[bytes]:
    old = socket.getdefaulttimeout()
    socket.setdefaulttimeout(FETCH_TIMEOUT)
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "SoCPlanningAgent/2.0 (+https://github.com/johnsonlu1973/tensorflow)",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
        })
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as r:
            return r.read(500_000)
    except Exception as e:
        print(f"    ⚠ fetch failed {url}: {e}")
        return None
    finally:
        socket.setdefaulttimeout(old)


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

def _parse_date(s: str) -> Optional[datetime]:
    if not s:
        return None
    s = s.strip()
    # ISO 8601
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S%z"):
        try:
            dt = datetime.strptime(s[:25], fmt[:len(s[:25])])
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
        except ValueError:
            pass
    # RFC 2822
    try:
        return parsedate_to_datetime(s)
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# RSS / Atom parser
# ---------------------------------------------------------------------------

def _parse_feed(raw: bytes, source_name: str) -> list:
    articles = []
    try:
        root = ET.fromstring(raw.decode("utf-8", errors="replace"))
    except ET.ParseError:
        return []

    tag = root.tag.lower()

    if "feed" in tag:
        # Atom
        for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
            title = (entry.findtext("{http://www.w3.org/2005/Atom}title") or "").strip()
            link_el = entry.find("{http://www.w3.org/2005/Atom}link")
            url = ""
            if link_el is not None:
                url = link_el.get("href", "") or link_el.text or ""
            pub = (entry.findtext("{http://www.w3.org/2005/Atom}published") or
                   entry.findtext("{http://www.w3.org/2005/Atom}updated") or "")
            summary = (entry.findtext("{http://www.w3.org/2005/Atom}summary") or
                       entry.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") or "")
            articles.append({
                "title": title, "url": url.strip(),
                "source": source_name, "published": pub,
                "summary": _clean_html(summary),
            })
    else:
        # RSS 2.0
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            url   = (item.findtext("link") or "").strip()
            pub   = (item.findtext("pubDate") or item.findtext("{http://purl.org/dc/elements/1.1/}date") or "")
            summary = (item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") or
                       item.findtext("description") or "")
            articles.append({
                "title": title, "url": url,
                "source": source_name, "published": pub,
                "summary": _clean_html(summary),
            })

    return articles


def _clean_html(text: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()[:800]


# ---------------------------------------------------------------------------
# Main collector class
# ---------------------------------------------------------------------------

class RSSCollector:
    def __init__(self, max_age_days: int = 1):
        self.max_age_days = max_age_days
        self.cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

    def _is_recent(self, pub_str: str) -> bool:
        dt = _parse_date(pub_str)
        if dt is None:
            return True  # include if date unparseable
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt >= self.cutoff

    def _fetch_category(self, feeds: list) -> list:
        articles = []
        for feed in feeds:
            raw = _fetch(feed["url"])
            if not raw:
                continue
            parsed = _parse_feed(raw, feed["name"])
            recent = [a for a in parsed if self._is_recent(a["published"])]
            print(f"      {feed['name']}: {len(recent)}/{len(parsed)} recent")
            articles.extend(recent)
        return articles

    def collect_daily(self) -> dict:
        """Fetch all category feeds. Returns {category: [article, ...]}."""
        result = {}
        for category, feeds in FEEDS.items():
            print(f"  [{category}] fetching {len(feeds)} feeds...")
            articles = self._fetch_category(feeds)
            # Deduplicate by URL
            seen = set()
            unique = []
            for a in articles:
                if a["url"] and a["url"] not in seen:
                    seen.add(a["url"])
                    unique.append(a)
            result[category] = unique
            print(f"    → {len(unique)} unique articles")
        return result

    def collect_3gpp_vendors(self) -> dict:
        """Fetch 3GPP vendor feeds (weekly)."""
        result = {}
        for category, feeds in FEEDS_3GPP.items():
            articles = self._fetch_category(feeds)
            result[category] = articles
        return result
