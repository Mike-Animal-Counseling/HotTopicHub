from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.models import DailyTopicBatch, Topic
from app.services.ai_summary_service import AISummaryService
from app.services.deduplication_service import DeduplicationService
from app.services.pipeline_types import TopicCluster
from app.services.source_adapters import (
    GitHubTrendingSourceAdapter,
    HackerNewsSourceAdapter,
    ProductHuntSourceAdapter,
    RSSSourceAdapter,
)
from app.services.topic_clustering_service import TopicClusteringService
from app.services.topic_filter_service import TopicFilterService


class TopicPipelineService:
    @staticmethod
    def _build_sources():
        return [
            HackerNewsSourceAdapter(),
            GitHubTrendingSourceAdapter(),
            ProductHuntSourceAdapter(),
            RSSSourceAdapter(
                "TechCrunch",
                "https://techcrunch.com/category/artificial-intelligence/feed/",
            ),
            RSSSourceAdapter("HuggingFace", "https://huggingface.co/blog/feed.xml"),
        ]

    @staticmethod
    def fetch_raw_articles(per_source_limit: int = 2):
        articles = []
        for source_adapter in TopicPipelineService._build_sources():
            articles.extend(source_adapter.fetch_top_items(per_source_limit))
        return articles

    @staticmethod
    def _pick_cluster_time(cluster: TopicCluster) -> datetime:
        if cluster.published_time:
            return cluster.published_time
        if cluster.articles:
            return max(article.published_time for article in cluster.articles)
        return datetime.now(timezone.utc)

    @staticmethod
    def generate_daily_topics(
        db: Session,
        date_key: str | None = None,
        per_source_limit: int = 4,
        per_source_reserve: int = 2,
        top_k: int = 10,
    ) -> int:
        normalized_date = date_key or date.today().isoformat()

        existing = db.query(Topic).filter(Topic.date_key == normalized_date).count()
        if existing > 0:
            return 0

        raw_articles = TopicPipelineService.fetch_raw_articles(per_source_limit)
        logger.info(
            f"[Pipeline {normalized_date}] Stage 1 (Fetch): {len(raw_articles)} raw articles "
            f"from 5 sources (per_source_limit={per_source_limit})"
        )

        deduplicated = DeduplicationService.deduplicate_articles(raw_articles)
        logger.info(
            f"[Pipeline {normalized_date}] Stage 2 (Deduplicate): {len(deduplicated)} after URL dedup (-{len(raw_articles) - len(deduplicated)})"
        )

        clusters = TopicClusteringService.cluster_articles(
            deduplicated, similarity_threshold=0.8
        )
        logger.info(
            f"[Pipeline {normalized_date}] Stage 3 (Cluster): {len(clusters)} clusters after title similarity merge"
        )

        ai_clusters = TopicFilterService.filter_ai_topics(clusters)
        logger.info(
            f"[Pipeline {normalized_date}] Stage 4 (Filter AI): {len(ai_clusters)} topics after AI keyword filter (-{len(clusters) - len(ai_clusters)})"
        )

        selected_clusters = TopicPipelineService._select_balanced_topics(
            ai_clusters,
            per_source_reserve=per_source_reserve,
            top_k=top_k,
        )
        logger.info(
            f"[Pipeline {normalized_date}] Stage 5 (Select): {len(selected_clusters)} topics selected with source-balanced strategy"
        )

        batch = DailyTopicBatch(date=normalized_date)
        db.add(batch)
        db.flush()

        source_counter: dict[str, int] = {}
        for cluster in selected_clusters:
            for article in cluster.articles:
                source = article.source
                source_counter[source] = source_counter.get(source, 0) + 1
            summary_payload = AISummaryService.generate_topic_summary(cluster)
            cluster_time = TopicPipelineService._pick_cluster_time(cluster)
            source_list = cluster.sources
            topic = Topic(
                title=cluster.title,
                summary=summary_payload["summary"],
                source_url=cluster.canonical_url,
                canonical_url=cluster.canonical_url,
                sources_json=json.dumps(source_list),
                published_time=cluster_time,
                cover_image=None,
                key_insights=summary_payload["key_insights"],
                why_it_matters=summary_payload["why_it_matters"],
                technical_summary=summary_payload["technical_summary"],
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                likes_count=0,
                comments_count=0,
                score=0,
                daily_rank=None,
                is_active=True,
                date_key=normalized_date,
                batch_id=batch.id,
            )
            db.add(topic)

        db.commit()

        source_summary = ", ".join(
            f"{source}({count})" for source, count in sorted(source_counter.items())
        )
        logger.info(
            f"[Pipeline {normalized_date}] COMPLETE: Created {len(selected_clusters)} topics | "
            f"Source distribution: {source_summary}"
        )

        return len(selected_clusters)

    @staticmethod
    def _select_balanced_topics(
        clusters: list[TopicCluster],
        per_source_reserve: int = 2,
        top_k: int = 10,
    ) -> list[TopicCluster]:
        if not clusters:
            return []

        source_map: dict[str, list[TopicCluster]] = {}
        for cluster in clusters:
            primary_source = (
                cluster.articles[0].source if cluster.articles else "unknown"
            )
            if primary_source not in source_map:
                source_map[primary_source] = []
            source_map[primary_source].append(cluster)

        reserved: list[TopicCluster] = []
        for source, source_clusters in source_map.items():
            sorted_clusters = sorted(
                source_clusters,
                key=lambda c: TopicPipelineService._pick_cluster_time(c),
                reverse=True,
            )
            reserved.extend(sorted_clusters[:per_source_reserve])

        reserved_ids = {id(c) for c in reserved}
        remaining = [c for c in clusters if id(c) not in reserved_ids]

        remaining_sorted = sorted(
            remaining,
            key=lambda c: TopicPipelineService._pick_cluster_time(c),
            reverse=True,
        )

        final = reserved + remaining_sorted
        seen = set()
        result: list[TopicCluster] = []
        for cluster in final:
            cluster_key = cluster.canonical_url or cluster.title
            if cluster_key not in seen:
                seen.add(cluster_key)
                result.append(cluster)
            if len(result) >= top_k:
                break

        return result
