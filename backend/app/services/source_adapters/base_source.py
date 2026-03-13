from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class RawArticle:
    title: str
    url: str
    source: str
    score: int
    published_time: datetime
    author: str | None = None
    summary: str | None = None
    engagement_count: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    stars: int = 0
    trend_score: float = 0.0
    source_rank: int | None = None
    top10_eligible: bool = True
    is_fallback: bool = False
    content_type: str = "other"
    builder_score: float = 0.0
    event_score: float = 0.0
    newsworthiness_score: float = 0.0
    is_primary_source: bool = False
    semantic_similarity: float = 0.0
    negative_similarity: float = 0.0
    prototype_label: str = ""


class BaseSourceAdapter(ABC):
    source_name: str

    @abstractmethod
    def fetch_top_items(
        self,
        limit: int,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
    ) -> list[RawArticle]:
        raise NotImplementedError

    def _fallback_articles(self, limit: int) -> list[RawArticle]:
        now = datetime.now(timezone.utc)
        return [
            RawArticle(
                title=f"{self.source_name} unavailable - fallback item {index + 1}",
                url=f"https://example.com/{self.source_name.lower()}-{index + 1}",
                source=self.source_name,
                score=max(100 - index * 5, 0),
                published_time=now,
                summary="Fallback item generated because source fetch failed.",
                top10_eligible=False,
                is_fallback=True,
            )
            for index in range(limit)
        ]
