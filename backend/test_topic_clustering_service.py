from datetime import datetime, timezone

from app.services.pipeline_types import TopicCluster
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


def test_should_merge_when_semantic_and_tokens_align(monkeypatch):
    lead = _article(
        "OpenAI launches Responses API for developers",
        "New API unifies tools, file search, and multimodal response generation.",
        "https://example.com/openai-responses",
    )
    cluster = TopicCluster(
        title=lead.title,
        canonical_url=lead.url,
        articles=[lead],
        published_time=lead.published_time,
    )
    candidate = _article(
        "OpenAI introduces the Responses API",
        "Developer API release combines tool use and multimodal responses.",
        "https://example.com/openai-responses-2",
    )

    monkeypatch.setattr(
        "app.services.topic_clustering_service.SemanticRelevanceService.cosine_similarity",
        lambda text_a, text_b: 0.9,
    )

    assert TopicClusteringService.should_merge(candidate, cluster) is True


def test_should_not_merge_when_topic_family_matches_but_entity_differs(monkeypatch):
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

    monkeypatch.setattr(
        "app.services.topic_clustering_service.SemanticRelevanceService.cosine_similarity",
        lambda text_a, text_b: 0.88,
    )

    assert TopicClusteringService.should_merge(candidate, cluster) is False


def test_cluster_articles_merges_semantic_rewrites(monkeypatch):
    monkeypatch.setattr(
        "app.services.topic_clustering_service.SemanticRelevanceService.cosine_similarity",
        lambda text_a, text_b: 0.91
        if "responses api" in text_a.lower() and "responses api" in text_b.lower()
        else 0.35,
    )

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
