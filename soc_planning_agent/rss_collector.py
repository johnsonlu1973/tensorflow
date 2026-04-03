"""RSS feed collector for SOC Planning Agent.

Uses only Python built-in libraries (urllib + xml.etree.ElementTree).
No external dependencies required.

Only vetted, high-credibility news sources are included.
No generic third-party blogs — only established tech news outlets,
industry publications, and official vendor/operator newsrooms.
"""
import socket
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

# Timeout for RSS fetch requests (seconds)
FETCH_TIMEOUT = 15

# Atom namespace
ATOM_NS = "http://www.w3.org/2005/Atom"

# Vetted daily news RSS sources by focus category.
# Format: {category: [(display_name, rss_url), ...]}
RSS_SOURCES_DAILY = {
    "agentic_ai": [
        ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
        ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/"),
        ("IEEE Spectrum", "https://spectrum.ieee.org/feeds/feed.rss"),
        ("MIT Technology Review", "https://www.technologyreview.com/feed/"),
        ("The Register AI", "https://www.theregister.com/emergent_tech/ai_plus_ml/headlines.atom"),
    ],
    "chips_soc": [
        ("EE Times", "https://www.eetimes.com/feed/"),
        ("Tom's Hardware", "https://www.tomshardware.com/feeds/all"),
        ("DigiTimes", "https://www.digitimes.com/rss/daily.xml"),
        ("SemiAnalysis", "https://semianalysis.com/feed/"),
        ("Semiconductor Engineering", "https://semiengineering.com/feed/"),
    ],
    "mobile": [
        ("GSMArena", "https://www.gsmarena.com/rss-news-articles.php3"),
        ("FierceWireless", "https://www.fiercewireless.com/rss/xml"),
        ("The Verge", "https://www.theverge.com/rss/index.xml"),
        ("Android Authority", "https://www.androidauthority.com/feed/"),
    ],
    "5g_cpe": [
        ("Light Reading", "https://www.lightreading.com/rss.xml"),
        ("RCR Wireless", "https://www.rcrwireless.com/feed"),
        ("FierceTelecom", "https://www.fiercetelecom.com/rss/xml"),
        ("TelecomTV", "https://www.telecomtv.com/rss/"),
        ("Telecom Paper", "https://www.telecompaper.com/rss/rss.aspx?s=1"),
    ],
    "csp_cloud": [
        ("The New Stack", "https://thenewstack.io/feed/"),
        ("SiliconANGLE", "https://siliconangle.com/feed/"),
        ("AWS Blog", "https://aws.amazon.com/blogs/aws/feed/"),
        ("Google Cloud Blog", "https://cloud.google.com/blog/rss/"),
        ("InfoQ", "https://feed.infoq.com/"),
    ],
}

# Vetted weekly vendor/operator RSS sources for 3GPP-related updates.
RSS_SOURCES_3GPP_VENDORS = {
    "vendors": [
        ("Nokia Newsroom", "https://www.nokia.com/about-us/news/releases/rss/"),
        ("Nokia Bell Labs Blog", "https://www.bell-labs.com/institute/blog/feed/"),
        ("Ericsson Newsroom", "https://www.ericsson.com/en/newsroom/rss"),
        ("Ericsson Technology Review", "https://www.ericsson.com/en/technology-review/rss"),
        ("Qualcomm Newsroom", "https://www.qualcomm.com/news/rss"),
        ("MediaTek Newsroom", "https://www.mediatek.com/news-events/press-releases/rss"),
    ],
    "operators": [
        ("Verizon News", "https://www.verizon.com/about/news/rss.xml"),
        ("T-Mobile Newsroom", "https://www.t-mobile.com/news/feed"),
        ("Vodafone Newsroom", "https://newscentre.vodafone.co.uk/feed/"),
    ],
}

# Keyword filters per category — article must match at least one keyword.
CATEGORY_KEYWORDS = {
    "agentic_ai": [
        "agentic", "ai agent", "multi-agent", "autonomous agent",
        "llm", "large language model", "generative ai", "genai",
        "on-device ai", "edge ai", "inference", "copilot",
        "openai", "anthropic", "gemini", "claude",
    ],
    "chips_soc": [
        "soc", "system-on-chip", "chipset", "modem", "baseband",
        "qualcomm", "mediatek", "apple silicon", "exynos", "snapdragon",
        "dimensity", "processor", "npu", "ai accelerator",
        "semiconductor", "tsmc", "foundry", "arm", "risc-v",
    ],
    "mobile": [
        "smartphone", "mobile phone", "5g phone", "flagship",
        "android", "iphone", "handset", "galaxy", "pixel",
        "oem", "xiaomi", "oppo", "vivo", "honor",
    ],
    "5g_cpe": [
        "5g", "cpe", "fixed wireless", "fwa", "6g",
        "open ran", "o-ran", "vran", "network slicing",
        "mmwave", "sub-6ghz", "nr", "5g-advanced",
        "rel-18", "rel-19", "release 18", "release 19",
    ],
    "csp_cloud": [
        "cloud", "aws", "azure", "google cloud", "csp",
        "datacenter", "data center", "infrastructure",
        "kubernetes", "serverless", "edge computing",
        "cloud native", "hyperscaler",
    ],
    "vendors": [
        "5g", "ran", "radio", "baseband", "modem",
        "release 18", "release 19", "5g-advanced", "6g",
        "network", "antenna", "massive mimo",
    ],
    "operators": [
        "5g", "network", "spectrum", "deployment", "launch",
        "rollout", "commercial", "subscriber", "coverage",
    ],
}


def _parse_date(date_str: str):
    """Parse date string to UTC datetime. Returns None on failure."""
    if not date_str:
        return None
    # Try RFC 2822 (RSS pubDate)
    try:
        return parsedate_to_datetime(date_str).astimezone(timezone.utc)
    except Exception:
        pass
    # Try ISO 8601 (Atom published)
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(date_str[:19], fmt[:len(date_str)])
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return None


def _strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    import re
    return re.sub(r"<[^>]+>", " ", text).strip()


def _parse_feed_xml(xml_bytes: bytes, source_name: str) -> list:
    """Parse RSS 2.0 or Atom 1.0 XML. Returns list of article dicts."""
    articles = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return articles

    tag = root.tag.lower()

    # --- Atom 1.0 ---
    if "atom" in tag or root.tag == f"{{{ATOM_NS}}}feed":
        for entry in root.iter(f"{{{ATOM_NS}}}entry"):
            title = entry.findtext(f"{{{ATOM_NS}}}title", "").strip()
            link_el = entry.find(f"{{{ATOM_NS}}}link[@rel='alternate']")
            if link_el is None:
                link_el = entry.find(f"{{{ATOM_NS}}}link")
            url = link_el.get("href", "") if link_el is not None else ""
            summary = entry.findtext(f"{{{ATOM_NS}}}summary", "") or \
                      entry.findtext(f"{{{ATOM_NS}}}content", "")
            published = entry.findtext(f"{{{ATOM_NS}}}published", "") or \
                        entry.findtext(f"{{{ATOM_NS}}}updated", "")
            articles.append({
                "source": source_name,
                "title": _strip_html(title),
                "url": url,
                "summary": _strip_html(summary)[:800],
                "published": published,
                "_dt": _parse_date(published),
            })
        return articles

    # --- RSS 2.0 ---
    for item in root.iter("item"):
        title = item.findtext("title", "").strip()
        url = item.findtext("link", "").strip()
        description = item.findtext("description", "").strip()
        pub_date = item.findtext("pubDate", "").strip()
        articles.append({
            "source": source_name,
            "title": _strip_html(title),
            "url": url,
            "summary": _strip_html(description)[:800],
            "published": pub_date,
            "_dt": _parse_date(pub_date),
        })
    return articles


class RSSCollector:
    """Fetches and filters RSS articles from vetted sources.

    Uses only Python built-in libraries — no external dependencies.
    """

    def __init__(self, max_age_days: int = 1):
        self.max_age_days = max_age_days
        self.cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

    def _is_recent(self, article: dict) -> bool:
        dt = article.get("_dt")
        if dt is None:
            return True  # no date info — include by default
        return dt >= self.cutoff

    def _matches_keywords(self, article: dict, keywords: list) -> bool:
        if not keywords:
            return True
        text = (article.get("title", "") + " " + article.get("summary", "")).lower()
        return any(kw.lower() in text for kw in keywords)

    def fetch_feed(self, source_name: str, feed_url: str, keywords: list) -> list:
        """Fetch one RSS/Atom feed and return filtered recent articles."""
        try:
            req = urllib.request.Request(
                feed_url,
                headers={"User-Agent": "SOC-Planning-Agent/1.0"},
            )
            prev_timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(FETCH_TIMEOUT)
            try:
                with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
                    xml_bytes = resp.read()
            finally:
                socket.setdefaulttimeout(prev_timeout)

            articles = _parse_feed_xml(xml_bytes, source_name)
            filtered = [
                a for a in articles
                if self._is_recent(a) and self._matches_keywords(a, keywords)
            ]
            # Remove internal _dt key before returning
            for a in filtered:
                a.pop("_dt", None)
            return filtered

        except Exception as e:
            print(f"    ⚠ RSS error [{source_name}]: {e}")
            return []

    def collect_category(self, category: str, sources: list) -> list:
        """Fetch all feeds in a category; return combined article list."""
        keywords = CATEGORY_KEYWORDS.get(category, [])
        all_articles = []
        for source_name, feed_url in sources:
            articles = self.fetch_feed(source_name, feed_url, keywords)
            if articles:
                print(f"    ✓ {source_name}: {len(articles)} article(s)")
            else:
                print(f"    · {source_name}: 0 new articles")
            all_articles.extend(articles)
            time.sleep(1)  # polite delay
        return all_articles

    def collect_daily(self) -> dict:
        """Fetch all daily RSS categories. Returns {category: [articles]}."""
        results = {}
        for category, sources in RSS_SOURCES_DAILY.items():
            print(f"\n  📡 [{category}] ({len(sources)} sources)...")
            articles = self.collect_category(category, sources)
            results[category] = articles
            print(f"     → {len(articles)} total")
        return results

    def collect_3gpp_vendors(self) -> dict:
        """Fetch vendor/operator RSS for weekly 3GPP update (7-day lookback)."""
        results = {}
        weekly = RSSCollector(max_age_days=7)
        for category, sources in RSS_SOURCES_3GPP_VENDORS.items():
            print(f"\n  📡 [3gpp/{category}] ({len(sources)} sources)...")
            articles = weekly.collect_category(category, sources)
            results[category] = articles
            print(f"     → {len(articles)} total")
        return results
