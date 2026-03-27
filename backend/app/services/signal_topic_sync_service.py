from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import HourlyFeedItem, Topic
from app.services.topic_enrichment_service import TopicEnrichmentService


class SignalTopicSyncService:
    LOOKBACK_HOURS = 24

    @staticmethod
    def _topic_has_enrichment(topic: Topic | None) -> bool:
        if topic is None:
            return False
        return all(
            bool(value and value.strip())
            for value in (
                topic.summary,
                topic.key_insights,
                topic.why_it_matters,
                topic.technical_summary,
            )
        )

    @staticmethod
    def _coerce_datetime(value: datetime | None) -> datetime:
        if value is None:
            return datetime.now(timezone.utc)
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _resolve_primary_source(item: HourlyFeedItem) -> str | None:
        sources = item.sources
        return sources[0] if sources else None

    @staticmethod
    def _topic_identity_candidates(db: Session, item: HourlyFeedItem) -> list[Topic]:
        seen_ids: set[int] = set()
        candidates: list[Topic] = []

        def add_topics(topics: list[Topic]) -> None:
            for topic in topics:
                if topic.id in seen_ids:
                    continue
                seen_ids.add(topic.id)
                candidates.append(topic)

        if item.canonical_url:
            add_topics(
                db.query(Topic).filter(Topic.canonical_url == item.canonical_url).all()
            )
        if item.source_url:
            add_topics(db.query(Topic).filter(Topic.source_url == item.source_url).all())
        add_topics(
            db.query(Topic)
            .filter(
                Topic.title == item.title,
                Topic.primary_source == SignalTopicSyncService._resolve_primary_source(item),
            )
            .all()
        )

        candidates.sort(
            key=lambda topic: (
                topic.likes_count,
                topic.comments_count,
                topic.source_clicks_count,
                topic.updated_at,
                -topic.id,
            ),
            reverse=True,
        )
        return candidates

    @staticmethod
    def _merge_duplicate_topics(
        db: Session,
        primary: Topic,
        duplicates: list[Topic],
    ) -> None:
        for duplicate in duplicates:
            if duplicate.id == primary.id:
                continue
            duplicate.is_active = False
            duplicate.daily_rank = None

    @staticmethod
    def _find_existing_topic(db: Session, item: HourlyFeedItem) -> Topic | None:
        candidates = SignalTopicSyncService._topic_identity_candidates(db, item)
        if not candidates:
            return None
        primary = candidates[0]
        if len(candidates) > 1:
            SignalTopicSyncService._merge_duplicate_topics(db, primary, candidates[1:])
        return primary

    @staticmethod
    def find_topic_for_feed_item(db: Session, item: HourlyFeedItem) -> Topic | None:
        return SignalTopicSyncService._find_existing_topic(db, item)

    @staticmethod
    def sync_from_recent_hourly_feed(
        db: Session,
        now: datetime | None = None,
        force_reenrich: bool = False,
    ) -> dict[str, int]:
        now = SignalTopicSyncService._coerce_datetime(now)
        window_start = now - timedelta(hours=SignalTopicSyncService.LOOKBACK_HOURS)
        items = (
            db.query(HourlyFeedItem)
            .filter(
                HourlyFeedItem.created_at >= window_start,
                HourlyFeedItem.created_at <= now,
            )
            .order_by(HourlyFeedItem.created_at.desc())
            .all()
        )

        stats = {
            "processed_count": 0,
            "created_count": 0,
            "updated_count": 0,
            "enriched_count": 0,
            "reused_count": 0,
        }
        for item in items:
            stats["processed_count"] += 1
            topic = SignalTopicSyncService._find_existing_topic(db, item)
            created_at = SignalTopicSyncService._coerce_datetime(item.created_at)
            published_time = SignalTopicSyncService._coerce_datetime(
                item.published_time or item.created_at
            )
            sources = item.sources
            primary_source = SignalTopicSyncService._resolve_primary_source(item)
            reused_enrichment = (
                topic is not None
                and not force_reenrich
                and SignalTopicSyncService._topic_has_enrichment(topic)
            )
            enrichment = (
                {
                    "summary": topic.summary,
                    "key_insights": topic.key_insights,
                    "why_it_matters": topic.why_it_matters,
                    "technical_summary": topic.technical_summary,
                }
                if reused_enrichment
                else TopicEnrichmentService.build_from_feed_item(item)
            )
            if reused_enrichment:
                stats["reused_count"] += 1
            else:
                stats["enriched_count"] += 1

            if topic is None:
                topic = Topic(
                    title=item.title,
                    summary=enrichment["summary"],
                    source_url=item.source_url,
                    canonical_url=item.canonical_url,
                    sources_json=json.dumps(sources),
                    published_time=published_time,
                    cover_image=None,
                    key_insights=enrichment["key_insights"],
                    why_it_matters=enrichment["why_it_matters"],
                    technical_summary=enrichment["technical_summary"],
                    created_at=created_at,
                    updated_at=now,
                    likes_count=0,
                    comments_count=0,
                    source_clicks_count=0,
                    score=0,
                    primary_source=primary_source,
                    daily_rank=None,
                    is_active=True,
                    date_key=created_at.date().isoformat(),
                )
                db.add(topic)
                stats["created_count"] += 1
                continue

            topic.title = item.title
            topic.summary = enrichment["summary"]
            topic.source_url = item.source_url
            topic.canonical_url = item.canonical_url
            topic.sources_json = json.dumps(sources)
            topic.published_time = published_time
            topic.primary_source = primary_source
            topic.key_insights = enrichment["key_insights"]
            topic.why_it_matters = enrichment["why_it_matters"]
            topic.technical_summary = enrichment["technical_summary"]
            topic.updated_at = now
            topic.is_active = True
            stats["updated_count"] += 1

        db.commit()
        return stats
