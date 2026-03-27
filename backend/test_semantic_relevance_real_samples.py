from datetime import datetime, timezone

from app.services.pipeline_types import TopicCluster
from app.services.semantic_relevance_service import SemanticRelevanceService
from app.services.source_adapters.base_source import RawArticle
from app.services.topic_clustering_service import TopicClusteringService


def _article(title: str, summary: str, url: str) -> RawArticle:
    return RawArticle(
        title=title,
        summary=summary,
        url=url,
        source="HackerNews",
        score=100,
        published_time=datetime.now(timezone.utc),
    )


def test_transformer_embedding_backend_is_available():
    _, transformer_ready = SemanticRelevanceService._ensure_transformer()
    assert transformer_ready is True


def test_real_embedding_similarity_orders_samples_reasonably():
    same_event_score = SemanticRelevanceService.cosine_similarity(
        "OpenAI launches Responses API for developers",
        "OpenAI introduces the Responses API",
    )
    adjacent_topic_score = SemanticRelevanceService.cosine_similarity(
        "Anthropic launches Claude Code for terminal workflows",
        "OpenAI launches Codex CLI for terminal workflows",
    )
    unrelated_score = SemanticRelevanceService.cosine_similarity(
        "Vercel ships AI SDK update for multi-provider agents",
        "Apple releases new iPad accessories",
    )

    assert same_event_score >= 0.8
    assert same_event_score > adjacent_topic_score
    assert adjacent_topic_score > unrelated_score
    assert unrelated_score <= 0.35


def test_real_similarity_keeps_distinct_products_separate():
    lead = _article(
        "Anthropic launches Claude Code for terminal workflows",
        "New agentic coding tool targets terminal-first developers.",
        "https://example.com/claude-code",
    )
    cluster = TopicCluster(
        title=lead.title,
        canonical_url=lead.url,
        articles=[lead],
        published_time=lead.published_time,
    )
    candidate = _article(
        "OpenAI launches Codex CLI for terminal workflows",
        "A separate coding tool release focused on local developer tasks.",
        "https://example.com/codex-cli",
    )

    similarity = TopicClusteringService.cluster_similarity(candidate, cluster)

    assert similarity["semantic_similarity"] < 0.7
    assert TopicClusteringService.should_merge(candidate, cluster) is False


def test_real_cluster_articles_merges_rewritten_same_topic():
    articles = [
        _article(
            "OpenAI launches Responses API for developers",
            "New API unifies tools, file search, and multimodal response generation.",
            "https://example.com/openai-responses",
        ),
        _article(
            "OpenAI introduces the Responses API",
            "Developer API release combines tool use and multimodal responses.",
            "https://example.com/openai-responses-2",
        ),
        _article(
            "Anthropic launches Claude Code for terminal workflows",
            "New agentic coding tool targets terminal-first developers.",
            "https://example.com/claude-code",
        ),
    ]

    clusters = TopicClusteringService.cluster_articles(articles)

    assert len(clusters) == 2
    assert sorted(len(cluster.articles) for cluster in clusters) == [1, 2]
