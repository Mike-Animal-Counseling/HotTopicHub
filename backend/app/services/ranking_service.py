import json
import math
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Comment, Topic, TopicLike


class RankingService:
    @staticmethod
    def compute_score(
        likes_count: int,
        comments_count: int,
        published_time: datetime,
        number_of_sources: int,
    ) -> float:
        now = datetime.now(timezone.utc)
        topic_published = (
            published_time
            if published_time.tzinfo
            else published_time.replace(tzinfo=timezone.utc)
        )
        age_hours = max((now - topic_published).total_seconds() / 3600, 0)

        engagement = (3 * math.log1p(max(likes_count, 0))) + (
            1 * math.log1p(max(comments_count, 0))
        )
        source_boost = 0.2 * max(number_of_sources - 1, 0)
        freshness = math.exp(-(age_hours / 24))
        return (engagement + source_boost) * (0.6 + 0.4 * freshness)

    @staticmethod
    def extract_source_count(topic: Topic) -> int:
        if not topic.sources_json:
            return 1
        try:
            payload = json.loads(topic.sources_json)
        except Exception:
            return 1

        if not isinstance(payload, list):
            return 1
        return max(len({item for item in payload if item}), 1)

    @staticmethod
    def recompute_topic_aggregates(db: Session, topic_id: int) -> Topic | None:
        topic = db.query(Topic).filter(Topic.id == topic_id).first()
        if not topic:
            return None

        likes_count = db.query(TopicLike).filter(TopicLike.topic_id == topic_id).count()
        comments_count = (
            db.query(Comment)
            .filter(
                Comment.topic_id == topic_id,
                Comment.is_hidden.is_(False),
                Comment.moderation_status.in_(["approved", "pending_review"]),
            )
            .count()
        )

        topic.likes_count = likes_count
        topic.comments_count = comments_count
        topic.score = RankingService.compute_score(
            likes_count,
            comments_count,
            topic.published_time or topic.created_at,
            RankingService.extract_source_count(topic),
        )
        db.commit()
        db.refresh(topic)
        return topic

    @staticmethod
    def recompute_rankings(db: Session, date_key: str) -> list[Topic]:
        topics = (
            db.query(Topic)
            .filter(Topic.date_key == date_key, Topic.is_active.is_(True))
            .all()
        )

        for topic in topics:
            topic.score = RankingService.compute_score(
                topic.likes_count,
                topic.comments_count,
                topic.published_time or topic.created_at,
                RankingService.extract_source_count(topic),
            )

        topics = sorted(
            topics,
            key=lambda item: (item.score, item.updated_at),
            reverse=True,
        )

        for index, topic in enumerate(topics, start=1):
            topic.daily_rank = index

        db.commit()
        return topics

    @staticmethod
    def refresh_topic_and_rankings(db: Session, topic_id: int) -> Topic | None:
        topic = RankingService.recompute_topic_aggregates(db, topic_id)
        if not topic:
            return None
        RankingService.recompute_rankings(db, topic.date_key)
        db.refresh(topic)
        return topic
