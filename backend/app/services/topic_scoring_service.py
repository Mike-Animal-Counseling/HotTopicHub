from __future__ import annotations

import math

from app.services.pipeline_types import TopicCluster
from app.services.semantic_relevance_service import SemanticRelevanceService
from app.services.source_adapters.base_source import RawArticle


class TopicScoringService:
    BUILDER_KEYWORDS = {
        "ai",
        "agent",
        "agents",
        "llm",
        "model",
        "models",
        "inference",
        "rag",
        "embedding",
        "embeddings",
        "vector",
        "prompt",
        "workflow",
        "automation",
        "copilot",
        "sdk",
        "api",
        "developer",
        "builders",
        "openai",
        "anthropic",
        "cursor",
        "replicate",
        "vercel",
        "huggingface",
    }

    EVENT_KEYWORDS = {
        "launch",
        "launches",
        "launched",
        "release",
        "released",
        "announces",
        "announced",
        "introduces",
        "introducing",
        "debuts",
        "ships",
        "now available",
        "raises",
        "funding",
        "series a",
        "acquires",
        "acquisition",
        "partnership",
        "benchmark",
        "major update",
    }

    TYPE_KEYWORDS = {
        "news": {"report", "reports", "according to", "deal", "announcement", "news"},
        "funding": {"raises", "funding", "series a", "series b", "acquires"},
        "launch": {"launch", "launches", "launched", "debut", "ships", "available"},
        "platform_update": {"update", "api", "sdk", "model", "release", "announces"},
        "research": {"paper", "research", "benchmark", "study", "arxiv"},
        "repo": {"github", "open-source", "repo", "repository", "framework", "library"},
        "discussion": {"ask hn", "show hn", "discussion", "why", "thoughts", "opinion"},
        "tool": {"tool", "editor", "copilot", "assistant", "agent", "workflow"},
    }

    SOURCE_BOOSTS = {
        "OpenAI": 1.25,
        "Anthropic": 1.25,
        "Replicate": 1.15,
        "Vercel": 1.1,
        "HuggingFace": 1.1,
        "ProductHunt": 1.05,
        "HackerNews": 1.05,
        "Reddit": 0.95,
        "GitHub": 0.85,
        "TechCrunch": 1.12,
        "Lobsters": 1.02,
    }

    PRIMARY_SOURCES = {"OpenAI", "Anthropic", "Replicate", "Vercel", "HuggingFace"}
    TRUSTED_NEWS_SOURCES = {"HackerNews", "TechCrunch", "Lobsters"}
    TYPE_CAPS = {"repo": 2, "discussion": 2, "other": 1, "news": 4}
    SOURCE_CAPS = {
        "GitHub": 2,
        "Reddit": 2,
        "OpenAI": 2,
        "ProductHunt": 2,
        "Vercel": 2,
        "HuggingFace": 2,
        "Anthropic": 2,
        "Replicate": 2,
    }
    COMMUNITY_SOURCES = {"HackerNews", "Reddit", "Lobsters", "TechCrunch"}
    NEWSLIKE_TYPES = {"news", "platform_update", "funding", "research"}
    TOP10_BACKFILL_TYPES = {
        "news",
        "platform_update",
        "funding",
        "research",
        "launch",
        "tool",
        "repo",
    }
    PRODUCT_INTENT_PROTOTYPES = {
        "ai_builder_tools",
        "agentic_workflows",
        "rag_systems",
        "model_platforms",
        "ai_product_launches",
        "open_source_ai",
    }
    STRICT_WINNER_SOURCES = {"ProductHunt", "Reddit", "GitHub"}
    KEYWORD_BUCKETS = {
        "core_ai": {
            "ai",
            "artificial intelligence",
            "llm",
            "language model",
            "foundation model",
            "multimodal",
            "inference",
            "fine-tuning",
            "fine tuning",
        },
        "agentic": {
            "agent",
            "agents",
            "agentic",
            "tool use",
            "function calling",
            "workflow",
            "orchestration",
            "automation",
            "copilot",
        },
        "retrieval": {
            "rag",
            "retrieval",
            "vector",
            "embedding",
            "embeddings",
            "rerank",
            "search pipeline",
            "knowledge base",
        },
        "builder_product": {
            "api",
            "sdk",
            "platform",
            "developer",
            "tooling",
            "framework",
            "launch",
            "release",
            "assistant",
            "builder",
        },
        "ecosystem": {
            "openai",
            "anthropic",
            "huggingface",
            "replicate",
            "vercel",
            "cursor",
            "claude",
            "gpt",
            "gemini",
        },
    }
    NEGATIVE_KEYWORDS = {
        "career",
        "salary",
        "manager",
        "management",
        "interview prep",
        "operating system",
        "kernel",
        "javascript framework",
        "frontend",
        "backend",
        "personal blog",
    }

    @staticmethod
    def _normalize_text(article: RawArticle) -> str:
        return " ".join(
            part for part in [article.title or "", article.summary or ""] if part
        ).lower()

    @staticmethod
    def _split_text_fields(article: RawArticle) -> tuple[str, str]:
        title = (article.title or "").lower()
        body = (article.summary or "").lower()
        return title, body

    @staticmethod
    def _keyword_signal(title: str, body: str) -> tuple[float, float]:
        title_signal = 0.0
        body_signal = 0.0
        for keywords in TopicScoringService.KEYWORD_BUCKETS.values():
            title_hits = sum(1 for keyword in keywords if keyword in title)
            body_hits = sum(1 for keyword in keywords if keyword in body)
            title_signal += min(title_hits * 0.65, 1.3)
            body_signal += min(body_hits * 0.3, 0.9)

        negative_hits = sum(
            1
            for keyword in TopicScoringService.NEGATIVE_KEYWORDS
            if keyword in title or keyword in body
        )
        penalty = min(negative_hits * 0.35, 1.2)
        return max(title_signal - penalty, 0.0), max(body_signal - (penalty * 0.5), 0.0)

    @staticmethod
    def _detect_content_type(normalized: str, source: str) -> str:
        for content_type, keywords in TopicScoringService.TYPE_KEYWORDS.items():
            if any(keyword in normalized for keyword in keywords):
                return content_type
        if source in {"TechCrunch", "HackerNews", "Lobsters"} and any(
            keyword in normalized for keyword in TopicScoringService.EVENT_KEYWORDS
        ):
            return "news"
        if source == "GitHub":
            return "repo"
        if source in {"ProductHunt", "OpenAI", "Anthropic", "Replicate", "Vercel"}:
            return "launch"
        return "other"

    @staticmethod
    def score_article(article: RawArticle) -> RawArticle:
        normalized = TopicScoringService._normalize_text(article)
        title_text, body_text = TopicScoringService._split_text_fields(article)
        builder_matches = sum(
            1 for keyword in TopicScoringService.BUILDER_KEYWORDS if keyword in normalized
        )
        semantic_payload = SemanticRelevanceService.score_text(normalized, article.source)
        title_semantic_payload = SemanticRelevanceService.score_text(
            title_text,
            article.source,
        )
        event_matches = sum(
            1 for keyword in TopicScoringService.EVENT_KEYWORDS if keyword in normalized
        )
        content_type = TopicScoringService._detect_content_type(normalized, article.source)
        source_boost = TopicScoringService.SOURCE_BOOSTS.get(article.source, 1.0)
        heat_score = math.log1p(max(article.trend_score, 0.0)) + (
            0.35 * math.log1p(max(article.engagement_count, 0))
        )
        title_keyword_signal, body_keyword_signal = TopicScoringService._keyword_signal(
            title_text,
            body_text,
        )

        builder_score = (
            float(title_semantic_payload["builder_relevance_score"]) * 0.75
            + float(semantic_payload["builder_relevance_score"]) * 0.45
            + title_keyword_signal * 0.95
            + body_keyword_signal * 0.55
            + min(builder_matches * 0.12, 0.6)
        )
        if article.source in {"HuggingFace"}:
            builder_score += 0.25
        if article.source in TopicScoringService.TRUSTED_NEWS_SOURCES:
            builder_score += 0.08
        if article.source in TopicScoringService.PRIMARY_SOURCES:
            builder_score += 0.22

        event_score = min(event_matches * 1.1, 4.0)
        if content_type in {"news", "launch", "platform_update", "funding", "research"}:
            event_score += 1.2
        elif content_type == "tool":
            event_score += 0.8
        elif content_type == "repo":
            event_score += 0.2

        newsworthiness_score = (
            (heat_score * 0.45)
            + (builder_score * 0.3)
            + (event_score * 0.25)
        ) * source_boost

        article.content_type = content_type
        article.builder_score = round(builder_score, 3)
        article.event_score = round(event_score, 3)
        article.newsworthiness_score = round(newsworthiness_score, 3)
        article.is_primary_source = article.source in TopicScoringService.PRIMARY_SOURCES
        article.semantic_similarity = max(
            float(semantic_payload["semantic_similarity"]),
            float(title_semantic_payload["semantic_similarity"]),
        )
        article.negative_similarity = float(semantic_payload["negative_similarity"])
        article.prototype_label = str(title_semantic_payload["prototype_label"])
        article.top10_eligible = (
            not article.is_fallback and article.newsworthiness_score >= 1.4
        )
        return article

    @staticmethod
    def enrich_articles(articles: list[RawArticle]) -> list[RawArticle]:
        return [TopicScoringService.score_article(article) for article in articles]

    @staticmethod
    def cluster_score(cluster: TopicCluster) -> float:
        base = sum(article.newsworthiness_score for article in cluster.articles)
        cross_source_bonus = 0.5 * max(len(cluster.sources) - 1, 0)
        primary_bonus = 0.6 if any(article.is_primary_source for article in cluster.articles) else 0.0
        return round(base + cross_source_bonus + primary_bonus, 3)

    @staticmethod
    def cluster_content_type(cluster: TopicCluster) -> str:
        ranked = sorted(
            cluster.articles,
            key=lambda article: (
                article.newsworthiness_score,
                article.event_score,
                article.builder_score,
            ),
            reverse=True,
        )
        return ranked[0].content_type if ranked else "other"

    @staticmethod
    def cluster_builder_score(cluster: TopicCluster) -> float:
        if not cluster.articles:
            return 0.0
        return max(article.builder_score for article in cluster.articles)

    @staticmethod
    def cluster_type_bonus(cluster: TopicCluster) -> float:
        content_type = TopicScoringService.cluster_content_type(cluster)
        if content_type in TopicScoringService.NEWSLIKE_TYPES:
            return 0.8
        if content_type in {"launch", "tool"}:
            return 0.45
        if content_type == "repo":
            return -0.1
        if content_type == "discussion":
            return -0.15
        if content_type == "other":
            return -0.25
        return 0.0

    @staticmethod
    def cluster_is_primary_source(cluster: TopicCluster) -> bool:
        return any(article.is_primary_source for article in cluster.articles)

    @staticmethod
    def cluster_primary_source(cluster: TopicCluster) -> str:
        if not cluster.articles:
            return "unknown"
        return cluster.articles[0].source

    @staticmethod
    def cluster_lead_article(cluster: TopicCluster) -> RawArticle | None:
        if not cluster.articles:
            return None
        ranked = sorted(
            cluster.articles,
            key=lambda article: (
                article.newsworthiness_score,
                article.event_score,
                article.builder_score,
                article.semantic_similarity,
            ),
            reverse=True,
        )
        return ranked[0]

    @staticmethod
    def cluster_is_source_winner_eligible(cluster: TopicCluster) -> bool:
        primary_source = TopicScoringService.cluster_primary_source(cluster)
        builder_score = TopicScoringService.cluster_builder_score(cluster)
        content_type = TopicScoringService.cluster_content_type(cluster)
        cluster_score = TopicScoringService.cluster_score(cluster)
        lead = TopicScoringService.cluster_lead_article(cluster)
        semantic_similarity = lead.semantic_similarity if lead else 0.0
        negative_similarity = lead.negative_similarity if lead else 0.0
        prototype_label = lead.prototype_label if lead else ""

        if content_type == "other":
            return False

        if primary_source in TopicScoringService.PRIMARY_SOURCES:
            return builder_score >= 1.1 and cluster_score >= 1.2

        if primary_source in TopicScoringService.TRUSTED_NEWS_SOURCES:
            return (
                builder_score >= 1.15
                and (
                    content_type in TopicScoringService.NEWSLIKE_TYPES
                    or content_type in {"launch", "tool"}
                )
                and cluster_score >= 1.2
                and semantic_similarity >= 0.32
                and negative_similarity <= 0.45
                and prototype_label in TopicScoringService.PRODUCT_INTENT_PROTOTYPES
            )

        if primary_source == "ProductHunt":
            return (
                builder_score >= 1.75
                and content_type in {"launch", "tool", "platform_update"}
                and cluster_score >= 1.45
                and semantic_similarity >= 0.42
                and negative_similarity <= 0.4
                and prototype_label in TopicScoringService.PRODUCT_INTENT_PROTOTYPES
            )

        if primary_source == "Reddit":
            return (
                builder_score >= 1.8
                and content_type in {"news", "launch", "tool", "research", "platform_update"}
                and cluster_score >= 1.5
            )

        if primary_source == "GitHub":
            return (
                builder_score >= 1.7
                and content_type in {"repo", "tool", "platform_update", "research"}
                and cluster_score >= 1.45
            )

        return builder_score >= 1.35 and cluster_score >= 1.25

    @staticmethod
    def cluster_is_daily_hub_eligible(cluster: TopicCluster) -> bool:
        primary_source = TopicScoringService.cluster_primary_source(cluster)
        content_type = TopicScoringService.cluster_content_type(cluster)
        builder_score = TopicScoringService.cluster_builder_score(cluster)
        cluster_score = TopicScoringService.cluster_score(cluster)
        lead = TopicScoringService.cluster_lead_article(cluster)
        semantic_similarity = lead.semantic_similarity if lead else 0.0
        negative_similarity = lead.negative_similarity if lead else 0.0

        if content_type == "other":
            return False
        if primary_source in TopicScoringService.STRICT_WINNER_SOURCES:
            return TopicScoringService.cluster_is_source_winner_eligible(cluster)
        if primary_source in TopicScoringService.TRUSTED_NEWS_SOURCES:
            return (
                builder_score >= 1.0
                and cluster_score >= 1.1
                and content_type in TopicScoringService.TOP10_BACKFILL_TYPES
                and semantic_similarity >= 0.28
                and negative_similarity <= 0.55
                and lead is not None
                and lead.prototype_label in TopicScoringService.PRODUCT_INTENT_PROTOTYPES
            )
        return (
            builder_score >= 0.95
            and cluster_score >= 1.05
            and semantic_similarity >= 0.24
        )

    @staticmethod
    def filter_top10_clusters(
        clusters: list[TopicCluster],
        top_k: int = 10,
    ) -> list[TopicCluster]:
        if not clusters:
            return []

        scored = sorted(
            clusters,
            key=TopicScoringService.cluster_score,
            reverse=True,
        )
        strict: list[TopicCluster] = []
        relaxed: list[TopicCluster] = []
        soft: list[TopicCluster] = []
        backfill: list[TopicCluster] = []

        for cluster in scored:
            builder_score = TopicScoringService.cluster_builder_score(cluster)
            content_type = TopicScoringService.cluster_content_type(cluster)
            primary_source = TopicScoringService.cluster_primary_source(cluster)
            is_primary = TopicScoringService.cluster_is_primary_source(cluster)
            cluster_score = TopicScoringService.cluster_score(cluster)

            passes_strict = (
                builder_score >= 1.85
                or (is_primary and builder_score >= 1.35)
                or (content_type in {"launch", "platform_update", "tool"} and builder_score >= 1.45)
            )
            if content_type == "other":
                passes_strict = passes_strict and builder_score >= 2.15
            if primary_source in TopicScoringService.COMMUNITY_SOURCES:
                passes_strict = passes_strict and builder_score >= 1.95

            if passes_strict:
                strict.append(cluster)
                continue

            passes_relaxed = (
                builder_score >= 1.35
                and (
                    content_type in {"launch", "platform_update", "tool", "research", "funding", "news"}
                    or primary_source not in TopicScoringService.COMMUNITY_SOURCES
                    or primary_source in TopicScoringService.TRUSTED_NEWS_SOURCES
                )
            )
            if passes_relaxed:
                relaxed.append(cluster)
                continue

            passes_soft = (
                builder_score >= 0.95
                and content_type != "other"
                and (
                    content_type in {"launch", "platform_update", "tool", "research", "funding", "repo", "news"}
                    or primary_source in TopicScoringService.PRIMARY_SOURCES
                    or primary_source in TopicScoringService.TRUSTED_NEWS_SOURCES
                )
            )
            if passes_soft:
                soft.append(cluster)
                continue

            passes_backfill = (
                content_type in TopicScoringService.TOP10_BACKFILL_TYPES
                and builder_score >= 0.75
                and cluster_score >= 1.1
                and (
                    primary_source in TopicScoringService.PRIMARY_SOURCES
                    or primary_source in TopicScoringService.TRUSTED_NEWS_SOURCES
                    or content_type in TopicScoringService.NEWSLIKE_TYPES
                )
            )
            if passes_backfill:
                backfill.append(cluster)

        combined = strict + relaxed
        if len(combined) >= top_k:
            return combined

        supplemented = combined + soft
        if len(supplemented) >= max(top_k, 8):
            return supplemented

        supplemented = supplemented + [
            cluster for cluster in backfill if cluster not in supplemented
        ]
        if len(supplemented) >= top_k:
            return supplemented

        # Final fallback: keep obviously relevant non-"other" items, then trusted-news items.
        fallback = []
        for cluster in scored:
            if cluster in supplemented:
                continue
            builder_score = TopicScoringService.cluster_builder_score(cluster)
            content_type = TopicScoringService.cluster_content_type(cluster)
            primary_source = TopicScoringService.cluster_primary_source(cluster)
            if content_type != "other" and builder_score >= 0.7:
                fallback.append(cluster)
                continue
            if (
                primary_source in TopicScoringService.TRUSTED_NEWS_SOURCES
                and builder_score >= 0.6
                and TopicScoringService.cluster_score(cluster) >= 1.0
            ):
                fallback.append(cluster)

        return supplemented + fallback

    @staticmethod
    def filter_builder_clusters(
        clusters: list[TopicCluster],
        top_k: int = 10,
    ) -> list[TopicCluster]:
        if not clusters:
            return []

        scored = sorted(
            clusters,
            key=TopicScoringService.cluster_score,
            reverse=True,
        )
        strong = [
            cluster for cluster in scored if TopicScoringService.cluster_score(cluster) >= 1.7
        ]
        if len(strong) >= top_k:
            return strong

        medium = [
            cluster
            for cluster in scored
            if TopicScoringService.cluster_score(cluster) >= 1.15
            and cluster not in strong
        ]
        supplemented = strong + medium
        if len(supplemented) >= max(top_k, 8):
            return supplemented

        return scored[: max(top_k, 8)]
