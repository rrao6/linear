"""
Competitive intelligence source definitions.
Each source has a URL, scrape strategy, and extraction logic.
"""

# --- Competitor Channel Pages (scrape for channel counts and lineups) ---
COMPETITOR_SITES = {
    "samsung_tv_plus": {
        "name": "Samsung TV Plus",
        "url": "https://www.samsung.com/us/tvplus/",
        "type": "channel_page",
        "notes": "Reports 300+ channels as of Feb 2026",
    },
    "pluto_tv": {
        "name": "Pluto TV",
        "url": "https://pluto.tv/en/live-tv",
        "type": "channel_page",
        "notes": "Extensive lineup, categories visible on page",
    },
    "xumo": {
        "name": "Xumo Play",
        "url": "https://play.xumo.com/channels",
        "type": "channel_page",
        "notes": "200+ channels, 26 categories as of Feb 2026",
    },
    "roku_channel": {
        "name": "Roku Channel",
        "url": "https://therokuchannel.roku.com/live",
        "type": "channel_page",
        "notes": "May require JS rendering",
    },
    "vizio_watchfree": {
        "name": "Vizio WatchFree+",
        "url": "https://www.vizio.com/en/watchfreeplus",
        "type": "channel_page",
    },
    "lg_channels": {
        "name": "LG Channels",
        "url": "https://www.lg.com/us/lg-channels/",
        "type": "channel_page",
    },
    "plex": {
        "name": "Plex",
        "url": "https://www.plex.tv/live-tv/",
        "type": "channel_page",
    },
    "tubi": {
        "name": "Tubi",
        "url": "https://tubitv.com/live",
        "type": "channel_page",
        "notes": "~340 channels per user report",
    },
    "stirr": {
        "name": "Stirr",
        "url": "https://stirr.com",
        "type": "channel_page",
    },
    "distro_tv": {
        "name": "Distro TV",
        "url": "https://www.distro.tv/channels/",
        "type": "channel_page",
    },
}

# --- Industry News RSS Feeds ---
NEWS_FEEDS = {
    "nexttv": {
        "name": "NextTV",
        "rss": "https://www.nexttv.com/rss",
        "url": "https://www.nexttv.com",
        "topics": ["FAST", "streaming", "linear", "CTV"],
    },
    "streamtv_insider": {
        "name": "StreamTV Insider",
        "rss": "https://www.streamtvinsider.com/rss.xml",
        "url": "https://www.streamtvinsider.com",
        "topics": ["FAST", "streaming", "OTT"],
    },
    "variety_digital": {
        "name": "Variety - Digital",
        "rss": "https://variety.com/v/digital/feed/",
        "url": "https://variety.com",
        "topics": ["streaming", "Tubi", "Pluto", "Roku"],
    },
    "deadline_tv": {
        "name": "Deadline - TV",
        "rss": "https://deadline.com/category/tv/feed/",
        "url": "https://deadline.com",
        "topics": ["streaming", "linear", "FAST"],
    },
    "the_verge": {
        "name": "The Verge",
        "rss": "https://www.theverge.com/rss/index.xml",
        "url": "https://www.theverge.com",
        "topics": ["streaming", "TV", "Roku", "Amazon Fire TV"],
    },
    "cord_cutters": {
        "name": "Cord Cutters News",
        "rss": "https://cordcuttersnews.com/feed/",
        "url": "https://cordcuttersnews.com",
        "topics": ["FAST", "free streaming", "cord cutting", "Tubi", "Pluto"],
    },
    "adweek": {
        "name": "AdWeek",
        "rss": "https://www.adweek.com/feed/",
        "url": "https://www.adweek.com",
        "topics": ["CTV", "streaming advertising", "FAST"],
    },
    "digiday": {
        "name": "Digiday",
        "rss": "https://digiday.com/feed/",
        "url": "https://digiday.com",
        "topics": ["CTV advertising", "streaming", "FAST"],
    },
}

# --- Search Queries for Web Research ---
SEARCH_QUERIES = {
    "market_overview": [
        "FAST channels streaming market 2025 2026",
        "free ad-supported streaming television market size",
        "CTV advertising FAST revenue 2025",
        "Nielsen Gauge streaming share latest",
    ],
    "competitor_updates": [
        '"Pluto TV" channels 2025 2026 new',
        '"Samsung TV Plus" channels update 2025',
        '"Roku Channel" live sports 2025 2026',
        '"Amazon Fire TV" channels live tab 2025',
        '"YouTube TV" subscribers growth 2025',
        '"Xumo" channels update 2025',
        "Tubi linear channels 2025 2026",
        '"Vizio WatchFree" 2025 update',
    ],
    "sports": [
        "free sports streaming FAST 2025",
        "Roku Sports Hub 2025 2026",
        "Tubi NFL Fox sports 2025",
        "ESPN standalone streaming launch date",
        "NFL free streaming channels 2025",
    ],
    "oem_platform": [
        "Fire TV live tab integration 2025",
        "Roku live TV guide third party integration",
        "Samsung TV Plus default channels 2025",
        "Google TV Freeplay FAST channels",
        "Vizio Walmart shoppable TV 2025",
    ],
    "advertising": [
        "FAST CTV CPM rates 2025",
        "ad-supported streaming revenue per user",
        "FAST ad fill rate comparison",
        "CTV programmatic advertising 2025",
    ],
}

# --- Competitor Tracking Dimensions ---
TRACKING_DIMENSIONS = [
    "channel_count",
    "channel_categories",
    "platform_availability",
    "integration_level",
    "ad_model",
    "monthly_active_users",
    "subscriber_count",
    "sports_content",
    "news_content",
    "exclusive_deals",
    "recent_launches",
    "international_markets",
    "key_features",
    "pricing",
]
