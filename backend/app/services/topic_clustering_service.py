from __future__ import annotations

import re
import string
from difflib import SequenceMatcher

from app.services.pipeline_types import TopicCluster
from app.services.semantic_relevance_service import SemanticRelevanceService
from app.services.source_adapters.base_source import RawArticle


class TopicClusteringService:
    STOPWORDS = {
        "a",
        "an",
        "the",
        "and",
        "or",
        "to",
        "for",
        "of",
        "on",
        "in",
        "with",
        "by",
        "at",
        "from",
        "is",
        "are",
        "new",
        "launches",
        "releases",
        "announces",
    }
    GENERIC_TOKENS = {
        "ai",
        "llm",
        "agent",
        "agents",
        "tool",
        "tools",
        "app",
        "apps",
        "platform",
        "platforms",
        "api",
        "apis",
        "sdk",
        "launch",
        "launched",
        "update",
        "updates",
        "feature",
        "features",
        "model",
        "models",
        "assistant",
        "workflow",
        "workflows",
        "developer",
        "developers",
        "open",
        "source",
        "chatbot",
        "startup",
        "new",
    }
    EXACT_TITLE_THRESHOLD = 0.93
    STRONG_EMBEDDING_THRESHOLD = 0.9
    HYBRID_THRESHOLD = 0.74
    MIN_EMBEDDING_FLOOR = 0.68
    MIN_TITLE_FLOOR = 0.3
    MIN_TOKEN_OVERLAP_FLOOR = 0.12

    @staticmethod
    def normalize_title(title: str) -> str:
        text = title.lower()
        text = text.translate(str.maketrans("", "", string.punctuation))
        tokens = [token for token in re.split(r"\s+", text) if token]
        filtered = [
            token for token in tokens if token not in TopicClusteringService.STOPWORDS
        ]
        return " ".join(filtered)

    @staticmethod
    def _semantic_text(article: RawArticle) -> str:
        title = (article.title or "").strip()
        summary = (article.summary or "").strip()
        if summary:
            return f"{title}. {title}. {summary}"
        return f"{title}. {title}"

    @staticmethod
    def _cluster_semantic_text(cluster: TopicCluster) -> str:
        ranked_articles = sorted(
            cluster.articles,
            key=lambda article: (
                article.newsworthiness_score,
                article.event_score,
                article.builder_score,
                article.semantic_similarity,
            ),
            reverse=True,
        )
        lead = ranked_articles[0] if ranked_articles else None
        if lead is None:
            return cluster.title
        return TopicClusteringService._semantic_text(lead)

    @staticmethod
    def _informative_tokens(text: str) -> set[str]:
        normalized = TopicClusteringService.normalize_title(text)
        tokens = set(re.findall(r"[a-z0-9\-\+\.]+", normalized))
        return {
            token
            for token in tokens
            if len(token) >= 3
            and token not in TopicClusteringService.GENERIC_TOKENS
            and not token.isdigit()
        }

    @staticmethod
    def _token_overlap(article: RawArticle, cluster: TopicCluster) -> float:
        article_tokens = TopicClusteringService._informative_tokens(
            f"{article.title} {(article.summary or '')}"
        )
        cluster_tokens = TopicClusteringService._informative_tokens(
            f"{cluster.title} {TopicClusteringService._cluster_semantic_text(cluster)}"
        )
        if not article_tokens or not cluster_tokens:
            return 0.0
        intersection = article_tokens & cluster_tokens
        union = article_tokens | cluster_tokens
        if not union:
            return 0.0
        return len(intersection) / len(union)

    @staticmethod
    def title_similarity(title_a: str, title_b: str) -> float:
        normalized_a = TopicClusteringService.normalize_title(title_a)
        normalized_b = TopicClusteringService.normalize_title(title_b)
        if not normalized_a or not normalized_b:
            return 0.0
        return SequenceMatcher(None, normalized_a, normalized_b).ratio()

    @staticmethod
    def cluster_similarity(article: RawArticle, cluster: TopicCluster) -> dict[str, float]:
        title_similarity = TopicClusteringService.title_similarity(
            article.title, cluster.title
        )
        semantic_similarity = SemanticRelevanceService.cosine_similarity(
            TopicClusteringService._semantic_text(article),
            TopicClusteringService._cluster_semantic_text(cluster),
        )
        token_overlap = TopicClusteringService._token_overlap(article, cluster)
        hybrid_score = round(
            (semantic_similarity * 0.6)
            + (title_similarity * 0.25)
            + (token_overlap * 0.15),
            4,
        )
        return {
            "title_similarity": round(title_similarity, 4),
            "semantic_similarity": round(semantic_similarity, 4),
            "token_overlap": round(token_overlap, 4),
            "hybrid_score": hybrid_score,
        }

    @staticmethod
    def should_merge(article: RawArticle, cluster: TopicCluster) -> bool:
        similarity = TopicClusteringService.cluster_similarity(article, cluster)
        title_similarity = similarity["title_similarity"]
        semantic_similarity = similarity["semantic_similarity"]
        token_overlap = similarity["token_overlap"]
        hybrid_score = similarity["hybrid_score"]

        if title_similarity >= TopicClusteringService.EXACT_TITLE_THRESHOLD:
            return True
        if (
            semantic_similarity >= TopicClusteringService.STRONG_EMBEDDING_THRESHOLD
            and token_overlap >= TopicClusteringService.MIN_TOKEN_OVERLAP_FLOOR
        ):
            return True
        if semantic_similarity < TopicClusteringService.MIN_EMBEDDING_FLOOR:
            return False
        if (
            title_similarity < TopicClusteringService.MIN_TITLE_FLOOR
            and token_overlap < TopicClusteringService.MIN_TOKEN_OVERLAP_FLOOR
        ):
            return False
        return hybrid_score >= TopicClusteringService.HYBRID_THRESHOLD

    @staticmethod
    def cluster_articles(
        articles: list[RawArticle], similarity_threshold: float = 0.8
    ) -> list[TopicCluster]:
        ordered_articles = sorted(
            articles,
            key=lambda article: article.published_time,
            reverse=True,
        )
        clusters: list[TopicCluster] = []

        for article in ordered_articles:
            matched_cluster: TopicCluster | None = None
            best_score = 0.0

            for cluster in clusters:
                similarity = TopicClusteringService.cluster_similarity(article, cluster)
                hybrid_score = similarity["hybrid_score"]
                if (
                    hybrid_score > best_score
                    and (
                        TopicClusteringService.should_merge(article, cluster)
                        or similarity["title_similarity"] >= similarity_threshold
                    )
                ):
                    best_score = hybrid_score
                    matched_cluster = cluster

            if matched_cluster:
                matched_cluster.articles.append(article)
                if article.published_time > (
                    matched_cluster.published_time or article.published_time
                ):
                    matched_cluster.published_time = article.published_time
                    matched_cluster.canonical_url = article.url
            else:
                clusters.append(
                    TopicCluster(
                        title=article.title,
                        canonical_url=article.url,
                        articles=[article],
                        published_time=article.published_time,
                    )
                )

        return clusters
