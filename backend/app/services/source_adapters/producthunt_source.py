from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .base_source import RawArticle
from .rss_source import RSSSourceAdapter


class ProductHuntSourceAdapter(RSSSourceAdapter):
    def __init__(self):
        super().__init__(
            source_name="ProductHunt",
            feed_url="https://www.producthunt.com/feed",
        )

    def fetch_top_items(
        self,
        limit: int,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
    ) -> list[RawArticle]:
        window_end = window_end or datetime.now(timezone.utc)
        window_start = window_start or (window_end - timedelta(hours=36))
        now = window_end
        items = super().fetch_top_items(limit * 3, window_start=window_start, window_end=window_end)
        filtered: list[RawArticle] = []

        for rank, article in enumerate(items, start=1):
            if article.published_time < window_start or article.published_time >= window_end:
                continue
            age_hours = max((now - article.published_time).total_seconds() / 3600, 1.0)
            article.source_rank = rank
            article.engagement_count = article.engagement_count or max(60 - rank * 8, 5)
            article.trend_score = max(70 - rank * 10, 10) / age_hours
            article.top10_eligible = rank <= max(limit + 1, 5)
            filtered.append(article)
            if len(filtered) >= limit:
                break

        return filtered if filtered else items[:limit]
