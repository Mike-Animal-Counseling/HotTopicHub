from __future__ import annotations

from app.services.pipeline_types import TopicCluster


class TopicFilterService:
    AI_KEYWORDS = {
        "ai",
        "llm",
        "openai",
        "anthropic",
        "gpt",
        "claude",
        "model",
        "agent",
        "rag",
        "vector",
        "embedding",
        "startup",
        "yc",
        "funding",
        "developer",
        "github",
    }

    @staticmethod
    def _contains_ai_signal(text: str) -> bool:
        normalized = (text or "").lower()
        return any(keyword in normalized for keyword in TopicFilterService.AI_KEYWORDS)

    @staticmethod
    def filter_ai_topics(clusters: list[TopicCluster]) -> list[TopicCluster]:
        filtered: list[TopicCluster] = []
        for cluster in clusters:
            combined_text = " ".join(
                [cluster.title]
                + [article.title for article in cluster.articles]
                + [article.summary or "" for article in cluster.articles]
            )
            if TopicFilterService._contains_ai_signal(combined_text):
                filtered.append(cluster)
        return filtered
