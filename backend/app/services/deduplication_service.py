from __future__ import annotations

from app.services.source_adapters.base_source import RawArticle


class DeduplicationService:
    @staticmethod
    def _normalize_url(url: str) -> str:
        return (url or "").strip().rstrip("/").lower()

    @staticmethod
    def deduplicate_articles(raw_articles: list[RawArticle]) -> list[RawArticle]:
        deduplicated: list[RawArticle] = []
        seen_urls: set[str] = set()

        for article in raw_articles:
            normalized_url = DeduplicationService._normalize_url(article.url)
            if not normalized_url or normalized_url in seen_urls:
                continue
            seen_urls.add(normalized_url)
            deduplicated.append(article)

        return deduplicated
