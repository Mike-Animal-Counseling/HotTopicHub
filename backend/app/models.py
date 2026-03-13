import json
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Topic(Base):
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    summary = Column(Text, nullable=True)
    source_url = Column(String, nullable=True)
    canonical_url = Column(String, nullable=True)
    sources_json = Column(Text, nullable=True)
    published_time = Column(DateTime(timezone=True), nullable=True, index=True)
    cover_image = Column(String, nullable=True)
    key_insights = Column(Text, nullable=True)
    why_it_matters = Column(Text, nullable=True)
    technical_summary = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    likes_count = Column(Integer, nullable=False, default=0)
    comments_count = Column(Integer, nullable=False, default=0)
    source_clicks_count = Column(Integer, nullable=False, default=0)
    score = Column(Float, nullable=False, default=0)
    primary_source = Column(String, nullable=True)
    daily_rank = Column(Integer, nullable=True, index=True)

    is_active = Column(Boolean, nullable=False, default=True, index=True)
    date_key = Column(String, nullable=False, index=True)

    likes = relationship(
        "TopicLike", back_populates="topic", cascade="all, delete-orphan"
    )
    comments = relationship(
        "Comment", back_populates="topic", cascade="all, delete-orphan"
    )

    @property
    def sources(self) -> list[str]:
        if not self.sources_json:
            return []
        try:
            payload = json.loads(self.sources_json)
        except Exception:
            return []
        return payload if isinstance(payload, list) else []

    @property
    def source(self) -> str | None:
        if self.primary_source:
            return self.primary_source
        return self.sources[0] if self.sources else None


class HourlyFeedBatch(Base):
    __tablename__ = "hourly_feed_batches"

    id = Column(Integer, primary_key=True, index=True)
    hour_key = Column(String, nullable=False, unique=True, index=True)
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    items = relationship(
        "HourlyFeedItem", back_populates="batch", cascade="all, delete-orphan"
    )


class HourlyFeedItem(Base):
    __tablename__ = "hourly_feed_items"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(
        Integer, ForeignKey("hourly_feed_batches.id"), nullable=False, index=True
    )
    title = Column(String, nullable=False)
    summary = Column(Text, nullable=True)
    canonical_url = Column(String, nullable=True)
    source_url = Column(String, nullable=True)
    sources_json = Column(Text, nullable=True)
    published_time = Column(DateTime(timezone=True), nullable=True, index=True)
    content_type = Column(String, nullable=False, default="other")
    builder_score = Column(Float, nullable=False, default=0)
    event_score = Column(Float, nullable=False, default=0)
    newsworthiness_score = Column(Float, nullable=False, default=0)
    feed_score = Column(Float, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    batch = relationship("HourlyFeedBatch", back_populates="items")

    @property
    def sources(self) -> list[str]:
        if not self.sources_json:
            return []
        try:
            payload = json.loads(self.sources_json)
        except Exception:
            return []
        return payload if isinstance(payload, list) else []

class TopicLike(Base):
    __tablename__ = "topic_likes"
    __table_args__ = (
        UniqueConstraint("topic_id", "user_identifier", name="uq_topic_like"),
    )

    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False, index=True)
    user_identifier = Column(String, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    topic = relationship("Topic", back_populates="likes")


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False, index=True)
    user_identifier = Column(String, nullable=False, index=True)

    author_name = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    image_url = Column(String, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, index=True
    )
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    likes_count = Column(Integer, nullable=False, default=0)

    moderation_status = Column(String, nullable=False, default="approved", index=True)
    moderation_reason = Column(String, nullable=True)
    moderation_flags = Column(Text, nullable=True)
    is_hidden = Column(Boolean, nullable=False, default=False, index=True)

    topic = relationship("Topic", back_populates="comments")
    likes = relationship(
        "CommentLike", back_populates="comment", cascade="all, delete-orphan"
    )
    reports = relationship(
        "Report", back_populates="comment", cascade="all, delete-orphan"
    )


class CommentLike(Base):
    __tablename__ = "comment_likes"
    __table_args__ = (
        UniqueConstraint("comment_id", "user_identifier", name="uq_comment_like"),
    )

    id = Column(Integer, primary_key=True, index=True)
    comment_id = Column(Integer, ForeignKey("comments.id"), nullable=False, index=True)
    user_identifier = Column(String, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    comment = relationship("Comment", back_populates="likes")


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        UniqueConstraint(
            "comment_id", "reporter_identifier", name="uq_report_once_per_comment"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    comment_id = Column(Integer, ForeignKey("comments.id"), nullable=False, index=True)
    reporter_identifier = Column(String, nullable=False, index=True)
    reason = Column(String, nullable=False)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    status = Column(String, nullable=False, default="open", index=True)

    comment = relationship("Comment", back_populates="reports")


class ModerationLog(Base):
    __tablename__ = "moderation_logs"

    id = Column(Integer, primary_key=True, index=True)
    comment_id = Column(Integer, ForeignKey("comments.id"), nullable=True, index=True)
    source = Column(String, nullable=False)
    action = Column(String, nullable=False)
    result = Column(String, nullable=False)
    flags = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
