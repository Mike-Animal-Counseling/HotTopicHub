from __future__ import annotations

from datetime import datetime

from app.services.source_adapters import (
    GitHubTrendingSourceAdapter,
    HackerNewsSourceAdapter,
    ProductHuntSourceAdapter,
    RedditSourceAdapter,
    RSSSourceAdapter,
)


class SourceCollectionService:
    @staticmethod
    def build_sources():
        return [
            HackerNewsSourceAdapter(),
            GitHubTrendingSourceAdapter(),
            ProductHuntSourceAdapter(),
            RedditSourceAdapter(),
            RSSSourceAdapter("HuggingFace", "https://huggingface.co/blog/feed.xml"),
            RSSSourceAdapter(
                "TechCrunch",
                "https://techcrunch.com/category/artificial-intelligence/feed/",
            ),
            RSSSourceAdapter("Lobsters", "https://lobste.rs/rss"),
            RSSSourceAdapter("OpenAI", "https://openai.com/news/rss.xml"),
            RSSSourceAdapter("Anthropic", "https://www.anthropic.com/news/rss.xml"),
            RSSSourceAdapter("Replicate", "https://replicate.com/blog.atom"),
            RSSSourceAdapter("Vercel", "https://vercel.com/atom"),
        ]

    @staticmethod
    def fetch_raw_articles(
        per_source_limit: int = 2,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
    ):
        articles = []
        for source_adapter in SourceCollectionService.build_sources():
            articles.extend(
                source_adapter.fetch_top_items(
                    per_source_limit,
                    window_start=window_start,
                    window_end=window_end,
                )
            )
        return articles

    @staticmethod
    def _article_priority(article) -> tuple[float, datetime]:
        return (
            article.trend_score + article.engagement_count * 0.05,
            article.published_time,
        )

    @staticmethod
    def filter_candidate_articles(raw_articles: list, top_k: int) -> list:
        real_articles = [article for article in raw_articles if not article.is_fallback]
        candidate_target = max(top_k * 6, 30)
        primary = [article for article in real_articles if article.top10_eligible]
        if len(primary) >= candidate_target:
            return primary

        supplements = sorted(
            [article for article in real_articles if not article.top10_eligible],
            key=SourceCollectionService._article_priority,
            reverse=True,
        )
        needed = max(candidate_target - len(primary), 0)
        return primary + supplements[:needed]
