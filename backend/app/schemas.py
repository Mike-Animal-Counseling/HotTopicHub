from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ModerationStatus = Literal["approved", "pending_review", "rejected"]
ReportReason = Literal[
    "harassment",
    "hate",
    "spam",
    "violence",
    "self-harm",
    "sexual",
    "misinformation",
    "other",
]
AdminAction = Literal["approve", "reject", "hide", "restore"]


class TopicOut(BaseModel):
    id: int
    title: str
    source: str | None = None
    summary: str | None
    source_url: str | None
    canonical_url: str | None = None
    sources: list[str] = Field(default_factory=list)
    published_time: datetime | None = None
    cover_image: str | None = None
    key_insights: str | None = None
    why_it_matters: str | None = None
    technical_summary: str | None = None
    created_at: datetime
    updated_at: datetime
    likes_count: int
    comments_count: int
    source_clicks_count: int = 0
    score: float
    daily_rank: int | None
    is_active: bool
    date_key: str

    class Config:
        from_attributes = True


class TopicLikeRequest(BaseModel):
    user_identifier: str = Field(min_length=2, max_length=100)


class CommentCreate(BaseModel):
    author_name: str = Field(min_length=1, max_length=120)
    user_identifier: str = Field(min_length=2, max_length=100)
    text: str = Field(min_length=1, max_length=3000)
    image_url: str | None = None


class CommentUpdate(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=3000)
    image_url: str | None = None


class CommentOut(BaseModel):
    id: int
    topic_id: int
    author_name: str
    text: str
    image_url: str | None
    created_at: datetime
    updated_at: datetime
    likes_count: int
    moderation_status: ModerationStatus
    moderation_reason: str | None
    moderation_flags: str | None
    is_hidden: bool

    class Config:
        from_attributes = True


class RankedCommentOut(BaseModel):
    id: int
    author_name: str
    text: str
    likes_count: int
    created_at: datetime
    score: float
    highlight: str | None = None


class CommentLikeRequest(BaseModel):
    user_identifier: str = Field(min_length=2, max_length=100)


class ReportCreate(BaseModel):
    reporter_identifier: str = Field(min_length=2, max_length=100)
    reason: ReportReason
    details: str | None = None


class ReportOut(BaseModel):
    id: int
    comment_id: int
    reporter_identifier: str
    reason: ReportReason
    details: str | None
    created_at: datetime
    status: Literal["open", "resolved"]

    class Config:
        from_attributes = True


class ModerationQueueItem(BaseModel):
    id: int
    topic_id: int
    topic_title: str | None = None
    author_name: str
    text: str
    image_url: str | None
    moderation_status: ModerationStatus
    moderation_reason: str | None
    moderation_flags: str | None
    is_hidden: bool
    created_at: datetime


class AdminCommentActionRequest(BaseModel):
    action: AdminAction
    reason: str | None = None


class ModerationLogOut(BaseModel):
    id: int
    comment_id: int | None
    source: Literal["auto", "admin"]
    action: str
    result: str
    flags: str | None
    reason: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class CommentCreateResponse(BaseModel):
    status: ModerationStatus
    message: str
    comment: CommentOut | None = None


class DailyTopSignalOut(BaseModel):
    id: int
    title: str
    source: str | None = None
    source_url: str | None = None
    canonical_url: str | None = None
    sources: list[str] = Field(default_factory=list)
    published_time: datetime | None = None
    summary: str | None = None
    key_insights: str | None = None
    why_it_matters: str | None = None
    technical_summary: str | None = None
    likes_count: int
    comments_count: int
    source_clicks_count: int = 0
    engagement_score: float
    created_at: datetime

    class Config:
        from_attributes = True


class DailyTopSignalsResponse(BaseModel):
    items: list[DailyTopSignalOut]


class DailyHistoryDayOut(BaseModel):
    date_key: str
    topics_count: int
    latest_topic_at: datetime | None = None


class DailyHistoryListResponse(BaseModel):
    items: list[DailyHistoryDayOut]


class HourlyFeedItemOut(BaseModel):
    id: int
    batch_id: int
    topic_id: int | None = None
    title: str
    summary: str | None
    canonical_url: str | None = None
    source_url: str | None = None
    sources: list[str] = Field(default_factory=list)
    published_time: datetime | None = None
    key_insights: str | None = None
    why_it_matters: str | None = None
    technical_summary: str | None = None
    likes_count: int = 0
    comments_count: int = 0
    source_clicks_count: int = 0
    content_type: str
    builder_score: float
    event_score: float
    newsworthiness_score: float
    feed_score: float
    created_at: datetime

    class Config:
        from_attributes = True


class HourlyFeedBatchOut(BaseModel):
    id: int
    hour_key: str
    window_start: datetime
    window_end: datetime
    created_at: datetime
    items_count: int


class HourlyFeedResponse(BaseModel):
    batch: HourlyFeedBatchOut
    items: list[HourlyFeedItemOut]


class HourlyFeedBatchListResponse(BaseModel):
    items: list[HourlyFeedBatchOut]


class CommentListResponse(BaseModel):
    items: list[CommentOut]

    class Config:
        from_attributes = True
