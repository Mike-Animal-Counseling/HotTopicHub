from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import HourlyFeedItem, Topic
from app.services.topic_enrichment_service import TopicEnrichmentService


class SignalTopicSyncService:
    LOOKBACK_HOURS = 24

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
    def _find_existing_topic(db: Session, item: HourlyFeedItem) -> Topic | None:
        if item.canonical_url:
            topic = db.query(Topic).filter(Topic.canonical_url == item.canonical_url).first()
            if topic:
                return topic
        if item.source_url:
            topic = db.query(Topic).filter(Topic.source_url == item.source_url).first()
            if topic:
                return topic
        return (
            db.query(Topic)
            .filter(
                Topic.title == item.title,
                Topic.primary_source == SignalTopicSyncService._resolve_primary_source(item),
            )
            .first()
        )

    @staticmethod
    def find_topic_for_feed_item(db: Session, item: HourlyFeedItem) -> Topic | None:
        return SignalTopicSyncService._find_existing_topic(db, item)

    @staticmethod
    def sync_from_recent_hourly_feed(
        db: Session,
        now: datetime | None = None,
    ) -> int:
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

        synced_count = 0
        for item in items:
            topic = SignalTopicSyncService._find_existing_topic(db, item)
            created_at = SignalTopicSyncService._coerce_datetime(item.created_at)
            published_time = SignalTopicSyncService._coerce_datetime(
                item.published_time or item.created_at
            )
            sources = item.sources
            primary_source = SignalTopicSyncService._resolve_primary_source(item)
            enrichment = TopicEnrichmentService.build_from_feed_item(item)

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
                synced_count += 1
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

        db.commit()
        return synced_count
