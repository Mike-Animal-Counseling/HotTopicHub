from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import Topic


@dataclass
class RankedSignal:
    topic: Topic
    engagement_score: float


@dataclass
class HistoryDay:
    date_key: str
    topics_count: int
    latest_topic_at: datetime | None


class DailyTopSignalsService:
    LOOKBACK_HOURS = 24
    RECENCY_BOOST_WINDOW_HOURS = 6
    RECENCY_BOOST_MAX = 3.0
    PER_SOURCE_CAP = 3
    MAX_RESULTS = 10

    @staticmethod
    def _coerce_datetime(value: datetime | None) -> datetime:
        if value is None:
            return datetime.now(timezone.utc)
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def compute_base_score(topic: Topic) -> float:
        return float(
            (3 * max(topic.likes_count, 0))
            + (5 * max(topic.comments_count, 0))
            + max(topic.source_clicks_count, 0)
        )

    @staticmethod
    def compute_recency_boost(topic: Topic, now: datetime | None = None) -> float:
        now = DailyTopSignalsService._coerce_datetime(now)
        created_at = DailyTopSignalsService._coerce_datetime(topic.created_at)
        age_hours = max((now - created_at).total_seconds() / 3600, 0.0)
        if age_hours >= DailyTopSignalsService.RECENCY_BOOST_WINDOW_HOURS:
            return 0.0
        ratio = 1 - (age_hours / DailyTopSignalsService.RECENCY_BOOST_WINDOW_HOURS)
        return round(ratio * DailyTopSignalsService.RECENCY_BOOST_MAX, 3)

    @staticmethod
    def compute_score(topic: Topic, now: datetime | None = None) -> float:
        return round(
            DailyTopSignalsService.compute_base_score(topic)
            + DailyTopSignalsService.compute_recency_boost(topic, now=now),
            3,
        )

    @staticmethod
    def list_last_24h_topics(db: Session, now: datetime | None = None) -> list[Topic]:
        now = DailyTopSignalsService._coerce_datetime(now)
        window_start = now - timedelta(hours=DailyTopSignalsService.LOOKBACK_HOURS)
        return (
            db.query(Topic)
            .filter(
                Topic.is_active.is_(True),
                Topic.created_at >= window_start,
                Topic.created_at <= now,
            )
            .all()
        )

    @staticmethod
    def list_topics_for_date(db: Session, date_key: str) -> list[Topic]:
        return (
            db.query(Topic)
            .filter(
                Topic.is_active.is_(True),
                Topic.date_key == date_key,
            )
            .all()
        )

    @staticmethod
    def list_history_days(db: Session, limit: int = 30) -> list[HistoryDay]:
        rows = (
            db.query(
                Topic.date_key,
                func.count(Topic.id),
                func.max(Topic.created_at),
            )
            .filter(Topic.is_active.is_(True))
            .group_by(Topic.date_key)
            .order_by(Topic.date_key.desc())
            .limit(limit)
            .all()
        )
        return [
            HistoryDay(
                date_key=row[0],
                topics_count=row[1],
                latest_topic_at=row[2],
            )
            for row in rows
        ]

    @staticmethod
    def rank_topics(
        topics: list[Topic],
        now: datetime | None = None,
        limit: int = MAX_RESULTS,
    ) -> list[RankedSignal]:
        now = DailyTopSignalsService._coerce_datetime(now)
        scored = [
            RankedSignal(topic=topic, engagement_score=DailyTopSignalsService.compute_score(topic, now=now))
            for topic in topics
        ]
        scored.sort(
            key=lambda item: (
                item.engagement_score,
                item.topic.comments_count,
                item.topic.likes_count,
                item.topic.source_clicks_count,
                DailyTopSignalsService._coerce_datetime(item.topic.created_at).timestamp(),
                item.topic.id,
            ),
            reverse=True,
        )

        selected: list[RankedSignal] = []
        source_counts: dict[str, int] = {}
        for item in scored:
            source = item.topic.source or "unknown"
            if source_counts.get(source, 0) >= DailyTopSignalsService.PER_SOURCE_CAP:
                continue
            selected.append(item)
            source_counts[source] = source_counts.get(source, 0) + 1
            if len(selected) >= limit:
                break
        return selected

    @staticmethod
    def get_daily_top_signals(
        db: Session,
        now: datetime | None = None,
        limit: int = MAX_RESULTS,
    ) -> list[RankedSignal]:
        topics = DailyTopSignalsService.list_last_24h_topics(db, now=now)
        return DailyTopSignalsService.rank_topics(topics, now=now, limit=limit)

    @staticmethod
    def get_signals_for_date(
        db: Session,
        date_key: str,
        limit: int = MAX_RESULTS,
    ) -> list[RankedSignal]:
        batch_date = date.fromisoformat(date_key)
        ranking_now = datetime.combine(
            batch_date,
            time.max,
            tzinfo=timezone.utc,
        )
        topics = DailyTopSignalsService.list_topics_for_date(db, date_key)
        return DailyTopSignalsService.rank_topics(topics, now=ranking_now, limit=limit)

    @staticmethod
    def record_source_click(db: Session, topic_id: int) -> Topic | None:
        topic = db.query(Topic).filter(Topic.id == topic_id).first()
        if not topic:
            return None
        topic.source_clicks_count = max(topic.source_clicks_count, 0) + 1
        db.commit()
        db.refresh(topic)
        return topic
