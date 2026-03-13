from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import HourlyFeedBatch, HourlyFeedItem
from app.services.pipeline_types import TopicCluster
from app.services.source_collection_service import SourceCollectionService
from app.services.topic_clustering_service import TopicClusteringService
from app.services.topic_scoring_service import TopicScoringService


class HourlyFeedService:
    FEED_WINDOW_HOURS = 1
    FEED_TOP_K = 24
    PER_SOURCE_LIMIT = 20
    MIN_CLUSTER_SCORE = 0.95
    SOURCE_CAPS = {
        "GitHub": 4,
        "Reddit": 4,
        "ProductHunt": 4,
        "OpenAI": 3,
        "Anthropic": 3,
    }
    TYPE_CAPS = {"repo": 5, "discussion": 4}

    @staticmethod
    def _normalize_hour_key(hour_key: str | None = None) -> str:
        if hour_key:
            parsed = datetime.fromisoformat(hour_key.replace("Z", "+00:00"))
        else:
            parsed = datetime.now(timezone.utc)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        normalized = parsed.astimezone(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        )
        return normalized.isoformat()

    @staticmethod
    def _resolve_window(hour_key: str | None = None) -> tuple[str, datetime, datetime]:
        normalized_hour = HourlyFeedService._normalize_hour_key(hour_key)
        window_end = datetime.fromisoformat(normalized_hour)
        window_start = window_end - timedelta(hours=HourlyFeedService.FEED_WINDOW_HOURS)
        return normalized_hour, window_start, window_end

    @staticmethod
    def _cluster_feed_score(cluster: TopicCluster) -> float:
        base = TopicScoringService.cluster_score(cluster)
        cluster_time = (
            cluster.published_time
            or max((article.published_time for article in cluster.articles), default=None)
            or datetime.now(timezone.utc)
        )
        now = datetime.now(timezone.utc)
        if cluster_time.tzinfo is None:
            cluster_time = cluster_time.replace(tzinfo=timezone.utc)
        age_hours = max((now - cluster_time).total_seconds() / 3600, 0)
        freshness_bonus = 2.2 * math.exp(-(age_hours / 1.2))
        return round(base + freshness_bonus, 3)

    @staticmethod
    def _select_feed_clusters(
        clusters: list[TopicCluster],
        top_k: int,
    ) -> list[tuple[TopicCluster, float]]:
        sorted_clusters = sorted(
            [
                (cluster, HourlyFeedService._cluster_feed_score(cluster))
                for cluster in clusters
                if HourlyFeedService._cluster_feed_score(cluster)
                >= HourlyFeedService.MIN_CLUSTER_SCORE
            ],
            key=lambda item: item[1],
            reverse=True,
        )
        if not sorted_clusters:
            return []

        selected: list[tuple[TopicCluster, float]] = []
        source_counts: dict[str, int] = {}
        type_counts: dict[str, int] = {}
        seen = set()

        for cluster, feed_score in sorted_clusters:
            cluster_key = cluster.canonical_url or cluster.title
            if cluster_key in seen:
                continue

            primary_source = cluster.articles[0].source if cluster.articles else "unknown"
            content_type = TopicScoringService.cluster_content_type(cluster)
            source_cap = HourlyFeedService.SOURCE_CAPS.get(primary_source, 5)
            type_cap = HourlyFeedService.TYPE_CAPS.get(content_type, 8)
            if source_counts.get(primary_source, 0) >= source_cap:
                continue
            if type_counts.get(content_type, 0) >= type_cap:
                continue

            seen.add(cluster_key)
            selected.append((cluster, feed_score))
            source_counts[primary_source] = source_counts.get(primary_source, 0) + 1
            type_counts[content_type] = type_counts.get(content_type, 0) + 1
            if len(selected) >= top_k:
                break

        if len(selected) < top_k:
            for cluster, feed_score in sorted_clusters:
                cluster_key = cluster.canonical_url or cluster.title
                if cluster_key in seen:
                    continue
                seen.add(cluster_key)
                selected.append((cluster, feed_score))
                if len(selected) >= top_k:
                    break

        return selected

    @staticmethod
    def _delete_existing_batch(db: Session, hour_key: str) -> None:
        batch = (
            db.query(HourlyFeedBatch)
            .filter(HourlyFeedBatch.hour_key == hour_key)
            .first()
        )
        if not batch:
            return
        db.delete(batch)
        db.commit()

    @staticmethod
    def batch_has_items(db: Session, batch: HourlyFeedBatch | None) -> bool:
        if not batch:
            return False
        count = (
            db.query(HourlyFeedItem)
            .filter(HourlyFeedItem.batch_id == batch.id)
            .count()
        )
        return count > 0

    @staticmethod
    def delete_batch_by_id(db: Session, batch_id: int) -> None:
        batch = db.query(HourlyFeedBatch).filter(HourlyFeedBatch.id == batch_id).first()
        if not batch:
            return
        db.delete(batch)
        db.commit()

    @staticmethod
    def prune_invalid_batches(db: Session) -> None:
        batches = db.query(HourlyFeedBatch).all()
        for batch in batches:
            if not HourlyFeedService.batch_has_items(db, batch):
                db.delete(batch)
        db.commit()

    @staticmethod
    def generate_hourly_feed(
        db: Session,
        hour_key: str | None = None,
        force: bool = False,
    ) -> HourlyFeedBatch:
        normalized_hour, window_start, window_end = HourlyFeedService._resolve_window(
            hour_key
        )
        existing = (
            db.query(HourlyFeedBatch)
            .filter(HourlyFeedBatch.hour_key == normalized_hour)
            .first()
        )
        if existing and not force and HourlyFeedService.batch_has_items(db, existing):
            return existing
        if existing:
            HourlyFeedService._delete_existing_batch(db, normalized_hour)

        raw_articles = SourceCollectionService.fetch_raw_articles(
            per_source_limit=HourlyFeedService.PER_SOURCE_LIMIT,
            window_start=window_start,
            window_end=window_end,
        )
        scored_articles = [
            article
            for article in TopicScoringService.enrich_articles(raw_articles)
            if not article.is_fallback
            and (
                article.builder_score >= 1.35
                or (article.is_primary_source and article.builder_score >= 1.1)
            )
            and not (
                article.content_type == "other" and article.builder_score < 1.8
            )
        ]
        deduplicated = SourceCollectionService.filter_candidate_articles(
            scored_articles,
            top_k=HourlyFeedService.FEED_TOP_K,
        )
        clusters = TopicClusteringService.cluster_articles(
            deduplicated, similarity_threshold=0.82
        )
        clusters = TopicScoringService.filter_builder_clusters(
            clusters,
            top_k=HourlyFeedService.FEED_TOP_K,
        )
        selected = HourlyFeedService._select_feed_clusters(
            clusters,
            HourlyFeedService.FEED_TOP_K,
        )

        batch = HourlyFeedBatch(
            hour_key=normalized_hour,
            window_start=window_start,
            window_end=window_end,
        )
        db.add(batch)
        db.flush()

        for cluster, feed_score in selected:
            ranked_articles = sorted(
                cluster.articles,
                key=lambda article: (
                    article.newsworthiness_score,
                    article.event_score,
                    article.builder_score,
                ),
                reverse=True,
            )
            lead = ranked_articles[0]
            item = HourlyFeedItem(
                batch_id=batch.id,
                title=cluster.title,
                summary=lead.summary,
                canonical_url=cluster.canonical_url,
                source_url=lead.url,
                sources_json=json.dumps(cluster.sources),
                published_time=cluster.published_time or lead.published_time,
                content_type=TopicScoringService.cluster_content_type(cluster),
                builder_score=max(article.builder_score for article in cluster.articles),
                event_score=max(article.event_score for article in cluster.articles),
                newsworthiness_score=max(
                    article.newsworthiness_score for article in cluster.articles
                ),
                feed_score=feed_score,
            )
            db.add(item)

        db.commit()
        db.refresh(batch)
        return batch

    @staticmethod
    def get_or_create_current_feed(db: Session) -> HourlyFeedBatch:
        normalized_hour = HourlyFeedService._normalize_hour_key()
        existing = (
            db.query(HourlyFeedBatch)
            .filter(HourlyFeedBatch.hour_key == normalized_hour)
            .first()
        )
        if existing and HourlyFeedService.batch_has_items(db, existing):
            return existing
        if existing and not HourlyFeedService.batch_has_items(db, existing):
            HourlyFeedService._delete_existing_batch(db, normalized_hour)
        return HourlyFeedService.generate_hourly_feed(db, normalized_hour)
