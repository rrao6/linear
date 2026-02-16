"""
Data models for the competitive intelligence pipeline.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
import hashlib
import json


@dataclass
class ArticleCandidate:
    """Raw article from RSS or web search."""
    competitor_id: str
    source_label: str
    title: str
    url: str
    published_at: str = ""
    snippet: str = ""
    hash: str = ""

    def __post_init__(self):
        if not self.hash:
            raw = f"{self.title.lower().strip()}{self.url.strip()}"
            self.hash = hashlib.sha256(raw.encode()).hexdigest()[:16]

    def to_dict(self):
        return asdict(self)


@dataclass
class ClassifiedIntel:
    """Article after classification by the AI classifier."""
    article_hash: str
    competitor_id: str
    title: str
    url: str
    summary: str = ""
    category: str = "general"  # strategic, product, content, marketing, pricing, partnership, earnings
    relevance_score: float = 0.0  # 1-10: how relevant to Tubi/FAST
    impact_score: float = 0.0  # 1-10: potential competitive impact
    entities: list = field(default_factory=list)
    source_count: int = 1
    published_at: str = ""

    def to_dict(self):
        return asdict(self)


@dataclass
class ThreatAssessment:
    """Output from threat analysis agent."""
    intel_hash: str
    threat_type: str = ""  # direct, indirect, potential, existential
    severity: float = 0.0  # 1-10
    description: str = ""
    defensive_action: str = ""
    timeframe: str = ""  # immediate, short_term, medium_term, long_term

    def to_dict(self):
        return asdict(self)


@dataclass
class Opportunity:
    """Output from opportunity analysis agent."""
    intel_hash: str
    opportunity_type: str = ""  # content, feature, market, partnership, technology
    potential_value: float = 0.0  # 1-10
    feasibility: float = 0.0  # 1-10
    description: str = ""
    action_items: list = field(default_factory=list)
    competitor_gap: str = ""

    @property
    def priority_score(self):
        return (self.potential_value * self.feasibility) / 10.0

    def to_dict(self):
        return asdict(self)


@dataclass
class Trend:
    """Output from trend tracking agent."""
    name: str = ""
    category: str = ""  # technology, content, distribution, monetization, audience
    direction: str = ""  # accelerating, stable, declining, emerging
    strength: float = 0.0  # 1-10
    description: str = ""
    prediction: str = ""
    timeframe: str = ""
    supporting_intel: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


@dataclass
class CompetitorProfile:
    """Synthesized competitor profile."""
    competitor_id: str
    name: str = ""
    tier: int = 0
    channel_count: Optional[int] = None
    business_model: str = ""
    strengths: list = field(default_factory=list)
    weaknesses: list = field(default_factory=list)
    recent_moves: list = field(default_factory=list)
    strategy_focus: str = ""
    threat_level: float = 0.0  # 1-10
    last_updated: str = ""

    def to_dict(self):
        return asdict(self)


@dataclass
class ScanRun:
    """Metadata for a single pipeline run."""
    run_id: str = ""
    started_at: str = ""
    finished_at: str = ""
    status: str = "pending"  # pending, running, completed, failed
    articles_collected: int = 0
    articles_classified: int = 0
    threats_found: int = 0
    opportunities_found: int = 0
    trends_identified: int = 0
    report_path: str = ""

    def __post_init__(self):
        if not self.run_id:
            self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        if not self.started_at:
            self.started_at = datetime.now().isoformat()

    def to_dict(self):
        return asdict(self)
