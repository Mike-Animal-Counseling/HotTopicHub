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


class BaseSourceAdapter(ABC):
    source_name: str

    @abstractmethod
    def fetch_top_items(self, limit: int) -> list[RawArticle]:
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
            )
            for index in range(limit)
        ]
