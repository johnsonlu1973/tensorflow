"""RSS feed collector for SOC Planning Agent.

Only vetted, high-credibility news sources are included.
No generic third-party blogs — only established tech news outlets,
industry publications, and official vendor/operator newsrooms.
"""
import socket
import time
from datetime import datetime, timedelta, timezone

import feedparser

# Timeout for RSS fetch requests (seconds)
FETCH_TIMEOUT = 15

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
        ("GSMA Intelligence Blog", "https://data.gsmaintelligence.com/research/research/rss"),
        ("Verizon News", "https://www.verizon.com/about/news/rss.xml"),
        ("T-Mobile Newsroom", "https://www.t-mobile.com/news/feed"),
        ("Vodafone Newsroom", "https://newscentre.vodafone.co.uk/feed/"),
    ],
}

# Keyword filters per category — article must match at least one keyword.
# Applied to title + summary text (case-insensitive).
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


class RSSCollector:
    """Fetches and filters RSS articles from vetted sources."""

    def __init__(self, max_age_days: int = 1):
        self.max_age_days = max_age_days
        self.cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

    def _is_recent(self, entry) -> bool:
        """Return True if article was published within max_age_days."""
        for attr in ("published_parsed", "updated_parsed"):
            val = getattr(entry, attr, None)
            if val:
                try:
                    pub_dt = datetime(*val[:6], tzinfo=timezone.utc)
                    return pub_dt >= self.cutoff
                except Exception:
                    pass
        # No date info — include by default (can't filter)
        return True

    def _matches_keywords(self, entry, keywords: list) -> bool:
        """Return True if entry title or summary contains any keyword."""
        if not keywords:
            return True
        text = " ".join([
            getattr(entry, "title", ""),
            getattr(entry, "summary", ""),
            getattr(entry, "description", ""),
        ]).lower()
        return any(kw.lower() in text for kw in keywords)

    def fetch_feed(self, source_name: str, feed_url: str, keywords: list) -> list:
        """Fetch one RSS feed; return list of matching recent articles."""
        articles = []
        prev_timeout = socket.getdefaulttimeout()
        try:
            socket.setdefaulttimeout(FETCH_TIMEOUT)
            feed = feedparser.parse(
                feed_url,
                request_headers={"User-Agent": "SOC-Planning-Agent/1.0"},
            )
            for entry in feed.entries:
                if not self._is_recent(entry):
                    continue
                if not self._matches_keywords(entry, keywords):
                    continue
                articles.append({
                    "source": source_name,
                    "title": getattr(entry, "title", "No title").strip(),
                    "url": getattr(entry, "link", ""),
                    "summary": getattr(
                        entry, "summary",
                        getattr(entry, "description", "")
                    )[:800].strip(),
                    "published": str(getattr(entry, "published", "")),
                })
        except Exception as e:
            print(f"  ⚠ RSS error [{source_name}]: {e}")
        finally:
            socket.setdefaulttimeout(prev_timeout)
        return articles

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
            time.sleep(1)  # polite delay between RSS requests
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
        """Fetch vendor/operator RSS for weekly 3GPP update. Returns {category: [articles]}."""
        results = {}
        for category, sources in RSS_SOURCES_3GPP_VENDORS.items():
            print(f"\n  📡 [3gpp/{category}] ({len(sources)} sources)...")
            # Weekly fetch — look back 7 days
            collector = RSSCollector(max_age_days=7)
            articles = collector.collect_category(category, sources)
            results[category] = articles
            print(f"     → {len(articles)} total")
        return results
