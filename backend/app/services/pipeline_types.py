from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.services.source_adapters.base_source import RawArticle


@dataclass
class TopicCluster:
    title: str
    canonical_url: str
    articles: list[RawArticle] = field(default_factory=list)
    published_time: datetime | None = None

    @property
    def sources(self) -> list[str]:
        return sorted({article.source for article in self.articles})
