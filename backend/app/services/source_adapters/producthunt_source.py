from __future__ import annotations

from .base_source import RawArticle
from .rss_source import RSSSourceAdapter


class ProductHuntSourceAdapter(RSSSourceAdapter):
    def __init__(self):
        super().__init__(
            source_name="ProductHunt",
            feed_url="https://www.producthunt.com/feed",
        )

    def fetch_top_items(self, limit: int) -> list[RawArticle]:
        return super().fetch_top_items(limit)
