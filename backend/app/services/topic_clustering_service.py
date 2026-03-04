from __future__ import annotations

import re
import string
from difflib import SequenceMatcher

from app.services.pipeline_types import TopicCluster
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
    def title_similarity(title_a: str, title_b: str) -> float:
        normalized_a = TopicClusteringService.normalize_title(title_a)
        normalized_b = TopicClusteringService.normalize_title(title_b)
        if not normalized_a or not normalized_b:
            return 0.0
        return SequenceMatcher(None, normalized_a, normalized_b).ratio()

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
                score = TopicClusteringService.title_similarity(
                    article.title, cluster.title
                )
                if score > best_score and score >= similarity_threshold:
                    best_score = score
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
