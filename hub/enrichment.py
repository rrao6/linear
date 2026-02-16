"""Metadata enrichment layer for feedback signals.

Uses OpenAI gpt-4o to extract structured metadata from raw feedback text:
entities, user context, product areas, actionability, and competitive mentions.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from openai import OpenAI

from .config import OPENAI_API_KEY

logger = logging.getLogger(__name__)

ENRICHMENT_PROMPT = """\
You are analyzing user feedback about Tubi, a free ad-supported streaming TV (FAST) service.
Extract structured metadata from the following feedback text.

Feedback text: {text}
Source: {source}
Additional context: {metadata}

Return a JSON object with these exact keys:

{{
  "entities": {{
    "channels": [],
    "platforms": [],
    "features": [],
    "competitors": []
  }},
  "user_context": {{
    "is_new_user": false,
    "is_power_user": false,
    "device_mentioned": "",
    "usage_pattern": ""
  }},
  "product_areas": [],
  "actionability": {{
    "is_feature_request": false,
    "is_bug_report": false,
    "is_churn_risk": false,
    "is_praise": false,
    "suggested_fix": ""
  }},
  "competitive_mention": null
}}

Rules:
- "channels": specific channel names mentioned (e.g., "ION", "Dateline 24/7", "NBC News NOW")
- "platforms": devices/platforms mentioned (e.g., "Roku", "Fire TV", "Samsung TV", "iOS", "Android")
- "features": UI/product features mentioned (e.g., "EPG grid", "search", "On Now row", "favorites")
- "competitors": competitor services mentioned (e.g., "Pluto TV", "YouTube TV", "Roku Channel", "Xumo")
- "product_areas": list from ONLY these values: "epg_grid", "channel_switching", "on_now_row", "search", "ad_breaks", "content_quality", "app_performance", "deeplinks", "live_tv", "vod", "recommendations", "ui_navigation", "playback", "account", "notifications", "guide", "remote_control", "casting", "subtitles", "audio"
- "is_new_user": true if text suggests the user recently started using Tubi
- "is_power_user": true if text suggests heavy/daily usage
- "device_mentioned": the specific device if mentioned, empty string if not
- "usage_pattern": brief description of how they use the service (e.g., "daily linear viewer", "occasional VOD watcher")
- "is_churn_risk": true if user expresses intent to leave, frustration suggesting abandonment, or comparison favoring a competitor
- "competitive_mention": set to {{"competitor": "name", "comparison": "better"|"worse"|"same", "feature_compared": "what"}} if a competitor is directly compared to Tubi, otherwise null

Return ONLY the JSON object, no markdown formatting or explanation."""


def enrich_feedback(text: str, source: str = "", metadata: Optional[dict] = None) -> dict:
    """Extract rich metadata from feedback text using OpenAI gpt-4o.

    Args:
        text: The raw feedback text.
        source: Where the feedback came from (reddit, appstore, etc.).
        metadata: Any additional context about the feedback.

    Returns:
        Dict with keys: entities, user_context, product_areas, actionability, competitive_mention.
        Returns a default/empty structure if OpenAI is unavailable or fails.
    """
    default = {
        "entities": {"channels": [], "platforms": [], "features": [], "competitors": []},
        "user_context": {"is_new_user": False, "is_power_user": False, "device_mentioned": "", "usage_pattern": ""},
        "product_areas": [],
        "actionability": {"is_feature_request": False, "is_bug_report": False, "is_churn_risk": False, "is_praise": False, "suggested_fix": ""},
        "competitive_mention": None,
    }

    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not configured, returning default enrichment")
        return default

    if not text or not text.strip():
        return default

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        prompt = ENRICHMENT_PROMPT.format(
            text=text,
            source=source,
            metadata=json.dumps(metadata or {}),
        )
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1000,
        )
        content = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

        result = json.loads(content)

        # Validate and fill missing keys with defaults
        for key in default:
            if key not in result:
                result[key] = default[key]

        return result

    except json.JSONDecodeError as e:
        logger.error("Failed to parse enrichment JSON: %s", e)
        return default
    except Exception as e:
        logger.error("Enrichment failed: %s", e)
        return default
