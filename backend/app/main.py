import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

from .database import engine, ensure_sqlite_schema, get_db
from . import models
from .models import (
    Comment,
    CommentLike,
    HourlyFeedBatch,
    HourlyFeedItem,
    ModerationLog,
    Report,
    Topic,
    TopicLike,
)
from .schemas import (
    AdminCommentActionRequest,
    CommentCreate,
    CommentCreateResponse,
    CommentLikeRequest,
    CommentListResponse,
    CommentOut,
    CommentUpdate,
    DailyTopSignalOut,
    DailyTopSignalsResponse,
    DailyHistoryDayOut,
    DailyHistoryListResponse,
    HourlyFeedBatchListResponse,
    HourlyFeedBatchOut,
    HourlyFeedItemOut,
    HourlyFeedResponse,
    ModerationLogOut,
    ModerationQueueItem,
    RankedCommentOut,
    ReportCreate,
    ReportOut,
    TopicLikeRequest,
    TopicOut,
)
from .services.moderation_service import ModerationService
from .services.comment_ranking_service import CommentRankingService
from .services.daily_top_signals_service import DailyTopSignalsService
from .services.hourly_feed_service import HourlyFeedService
from .services.ranking_service import RankingService
from .services.signal_topic_sync_service import SignalTopicSyncService

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dev-admin-token")


async def run_hourly_feed_refresh_loop():
    while True:
        db_gen = get_db()
        db = next(db_gen)
        try:
            HourlyFeedService.get_or_create_current_feed(db)
            SignalTopicSyncService.sync_from_recent_hourly_feed(db)
        except Exception as exc:
            logger.error(f"Hourly feed refresh error: {exc}", exc_info=True)
        finally:
            db_gen.close()

        now = datetime.now(timezone.utc)
        next_hour = (now + timedelta(hours=1)).replace(
            minute=0,
            second=0,
            microsecond=0,
        )
        sleep_seconds = max((next_hour - now).total_seconds(), 60)
        await asyncio.sleep(sleep_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    background_task = None
    db_gen = None
    try:
        logger.info("=== Application startup ===")
        models.Base.metadata.create_all(bind=engine)
        ensure_sqlite_schema()
        db_gen = get_db()
        db = next(db_gen)
        logger.info("Refreshing hourly realtime feed...")
        HourlyFeedService.get_or_create_current_feed(db)
        logger.info("Syncing signal topics from recent hourly feed...")
        SignalTopicSyncService.sync_from_recent_hourly_feed(db)
        logger.info("Preloading Detoxify model for comment moderation...")
        ModerationService._get_detoxify_model()
        logger.info("Detoxify model loaded successfully")
        background_task = asyncio.create_task(run_hourly_feed_refresh_loop())
        logger.info("=== Application startup complete ===")
    except Exception as e:
        logger.error(f"Startup error: {e}", exc_info=True)
    finally:
        if db_gen is not None:
            db_gen.close()

    yield

    if background_task:
        background_task.cancel()
        try:
            await background_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Comments API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_admin(x_admin_token: str | None = Header(default=None)):
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid admin token.")


def get_topic_or_404(db: Session, topic_id: int) -> Topic:
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


def get_comment_or_404(db: Session, comment_id: int) -> Comment:
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    return comment


def serialize_feed_batch(batch: HourlyFeedBatch) -> HourlyFeedBatchOut:
    return HourlyFeedBatchOut(
        id=batch.id,
        hour_key=batch.hour_key,
        window_start=batch.window_start,
        window_end=batch.window_end,
        created_at=batch.created_at,
        items_count=len(batch.items),
    )


def serialize_daily_top_signal(item) -> DailyTopSignalOut:
    topic = item.topic
    return DailyTopSignalOut(
        id=topic.id,
        title=topic.title,
        source=topic.source,
        source_url=topic.source_url,
        canonical_url=topic.canonical_url,
        sources=topic.sources,
        published_time=topic.published_time,
        summary=topic.summary,
        key_insights=topic.key_insights,
        why_it_matters=topic.why_it_matters,
        technical_summary=topic.technical_summary,
        likes_count=topic.likes_count,
        comments_count=topic.comments_count,
        source_clicks_count=topic.source_clicks_count,
        engagement_score=item.engagement_score,
        created_at=topic.created_at,
    )


def normalize_date_key(date_value: str) -> str:
    try:
        return datetime.fromisoformat(f"{date_value}T00:00:00+00:00").date().isoformat()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD") from exc


def serialize_feed_item(db: Session, item: HourlyFeedItem) -> HourlyFeedItemOut:
    topic = SignalTopicSyncService.find_topic_for_feed_item(db, item)
    return HourlyFeedItemOut(
        id=item.id,
        batch_id=item.batch_id,
        topic_id=topic.id if topic else None,
        title=topic.title if topic else item.title,
        summary=(topic.summary if topic and topic.summary else item.summary),
        canonical_url=topic.canonical_url if topic else item.canonical_url,
        source_url=topic.source_url if topic else item.source_url,
        sources=topic.sources if topic else item.sources,
        published_time=topic.published_time if topic else item.published_time,
        key_insights=topic.key_insights if topic else None,
        why_it_matters=topic.why_it_matters if topic else None,
        technical_summary=topic.technical_summary if topic else None,
        likes_count=topic.likes_count if topic else 0,
        comments_count=topic.comments_count if topic else 0,
        source_clicks_count=topic.source_clicks_count if topic else 0,
        content_type=item.content_type,
        builder_score=item.builder_score,
        event_score=item.event_score,
        newsworthiness_score=item.newsworthiness_score,
        feed_score=item.feed_score,
        created_at=item.created_at,
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/topics/daily-top-signals", response_model=DailyTopSignalsResponse)
def get_daily_top_signals(db: Session = Depends(get_db)):
    SignalTopicSyncService.sync_from_recent_hourly_feed(db)
    ranked = DailyTopSignalsService.get_daily_top_signals(db)
    items = [serialize_daily_top_signal(item) for item in ranked]
    return {"items": items}


@app.get("/api/topics/history", response_model=DailyHistoryListResponse)
def get_daily_signal_history(
    limit: int = Query(default=30, ge=1, le=180),
    db: Session = Depends(get_db),
):
    items = [
        DailyHistoryDayOut(
            date_key=item.date_key,
            topics_count=item.topics_count,
            latest_topic_at=item.latest_topic_at,
        )
        for item in DailyTopSignalsService.list_history_days(db, limit=limit)
    ]
    return {"items": items}


@app.get("/api/topics/history/{date_key}", response_model=DailyTopSignalsResponse)
def get_daily_signals_for_date(
    date_key: str,
    db: Session = Depends(get_db),
):
    normalized_date = normalize_date_key(date_key)
    ranked = DailyTopSignalsService.get_signals_for_date(db, normalized_date)
    return {"items": [serialize_daily_top_signal(item) for item in ranked]}


@app.get("/api/topics/{topic_id}", response_model=TopicOut)
def get_topic(topic_id: int, db: Session = Depends(get_db)):
    return get_topic_or_404(db, topic_id)


@app.get("/api/feed/realtime", response_model=HourlyFeedResponse)
def get_realtime_feed(
    hour_key: str | None = Query(default=None, alias="hour"),
    db: Session = Depends(get_db),
):
    if hour_key:
        batch = (
            db.query(HourlyFeedBatch)
            .filter(HourlyFeedBatch.hour_key == hour_key)
            .first()
        )
        if not batch:
            raise HTTPException(status_code=404, detail="Hourly feed batch not found")
        if not HourlyFeedService.batch_has_items(db, batch):
            batch = HourlyFeedService.generate_hourly_feed(
                db,
                hour_key=hour_key,
                force=True,
            )
    else:
        batch = HourlyFeedService.get_or_create_current_feed(db)
    SignalTopicSyncService.sync_from_recent_hourly_feed(db)

    items = (
        db.query(HourlyFeedItem)
        .filter(HourlyFeedItem.batch_id == batch.id)
        .order_by(HourlyFeedItem.feed_score.desc(), HourlyFeedItem.published_time.desc())
        .all()
    )
    return {
        "batch": serialize_feed_batch(batch),
        "items": [serialize_feed_item(db, item) for item in items],
    }


@app.post("/api/feed/realtime/refresh", response_model=HourlyFeedResponse)
def refresh_realtime_feed(
    hour_key: str | None = Query(default=None, alias="hour"),
    force: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    batch = HourlyFeedService.generate_hourly_feed(
        db,
        hour_key=hour_key,
        force=force,
    )
    SignalTopicSyncService.sync_from_recent_hourly_feed(db)
    items = (
        db.query(HourlyFeedItem)
        .filter(HourlyFeedItem.batch_id == batch.id)
        .order_by(HourlyFeedItem.feed_score.desc(), HourlyFeedItem.published_time.desc())
        .all()
    )
    return {
        "batch": serialize_feed_batch(batch),
        "items": [serialize_feed_item(db, item) for item in items],
    }


@app.get("/api/feed/history", response_model=HourlyFeedBatchListResponse)
def list_feed_history(
    limit: int = Query(default=24, ge=1, le=168),
    db: Session = Depends(get_db),
):
    HourlyFeedService.prune_invalid_batches(db)
    batches = (
        db.query(HourlyFeedBatch)
        .order_by(HourlyFeedBatch.window_end.desc())
        .all()
    )
    valid_batches = [
        batch for batch in batches if HourlyFeedService.batch_has_items(db, batch)
    ][:limit]
    return {"items": [serialize_feed_batch(batch) for batch in valid_batches]}


@app.post("/api/topics/{topic_id}/like")
def like_topic(topic_id: int, payload: TopicLikeRequest, db: Session = Depends(get_db)):
    get_topic_or_404(db, topic_id)
    like = TopicLike(topic_id=topic_id, user_identifier=payload.user_identifier)
    db.add(like)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Topic already liked by this user")

    topic = RankingService.refresh_topic_and_rankings(db, topic_id)
    return {
        "ok": True,
        "topic_id": topic_id,
        "likes_count": topic.likes_count if topic else 0,
    }


@app.post("/api/topics/{topic_id}/source-click")
def record_topic_source_click(topic_id: int, db: Session = Depends(get_db)):
    topic = DailyTopSignalsService.record_source_click(db, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    return {
        "ok": True,
        "topic_id": topic.id,
        "source_clicks_count": topic.source_clicks_count,
    }


@app.delete("/api/topics/{topic_id}/like")
def unlike_topic(
    topic_id: int,
    user_identifier: str = Query(..., min_length=2),
    db: Session = Depends(get_db),
):
    get_topic_or_404(db, topic_id)
    like = (
        db.query(TopicLike)
        .filter(
            TopicLike.topic_id == topic_id, TopicLike.user_identifier == user_identifier
        )
        .first()
    )
    if like:
        db.delete(like)
        db.commit()

    topic = RankingService.refresh_topic_and_rankings(db, topic_id)
    return {
        "ok": True,
        "topic_id": topic_id,
        "likes_count": topic.likes_count if topic else 0,
    }


@app.get("/api/topics/{topic_id}/comments", response_model=CommentListResponse)
def list_topic_comments(topic_id: int, db: Session = Depends(get_db)):
    get_topic_or_404(db, topic_id)
    items = (
        db.query(Comment)
        .filter(
            Comment.topic_id == topic_id,
            Comment.moderation_status == "approved",
            Comment.is_hidden.is_(False),
        )
        .order_by(Comment.created_at.desc())
        .all()
    )
    return {"items": items}


@app.get(
    "/api/topics/{topic_id}/comments/highlights",
    response_model=list[RankedCommentOut],
)
def list_ranked_topic_comments(topic_id: int, db: Session = Depends(get_db)):
    get_topic_or_404(db, topic_id)
    comments = (
        db.query(Comment)
        .filter(
            Comment.topic_id == topic_id,
            Comment.is_hidden.is_(False),
            Comment.moderation_status.in_(["approved", "pending_review"]),
        )
        .all()
    )
    ranked = CommentRankingService.rank_comments(comments)
    return [
        RankedCommentOut(
            id=item["comment"].id,
            author_name=item["comment"].author_name,
            text=item["comment"].text,
            likes_count=item["comment"].likes_count,
            created_at=item["comment"].created_at,
            score=item["score"],
            highlight=item["highlight"],
        )
        for item in ranked
    ]


@app.post("/api/topics/{topic_id}/comments", response_model=CommentCreateResponse)
def create_comment(
    topic_id: int, payload: CommentCreate, db: Session = Depends(get_db)
):
    get_topic_or_404(db, topic_id)

    moderation_result = ModerationService.run_auto_moderation(
        db,
        topic_id=topic_id,
        user_identifier=payload.user_identifier,
        text=payload.text,
        image_url=payload.image_url,
    )

    if moderation_result["status"] == "rejected":
        ModerationService.create_log(
            db,
            comment_id=None,
            source="auto",
            action="create_comment",
            result="rejected",
            flags=moderation_result["flags"],
            reason=moderation_result["reason"],
        )

        reject_flags = set(moderation_result.get("flags") or [])
        if (
            "rate_limit_30_seconds" in reject_flags
            or "rate_limit_5_minutes" in reject_flags
        ):
            detail_message = "You are posting comments too quickly. Please wait a moment and try again."
        else:
            detail_message = (
                "Your comment contains inappropriate language or harmful content. "
                "Please use respectful language."
            )

        raise HTTPException(
            status_code=400,
            detail=detail_message,
        )

    is_hidden = moderation_result["status"] == "pending_review"
    comment = Comment(
        topic_id=topic_id,
        user_identifier=payload.user_identifier,
        author_name=payload.author_name,
        text=payload.text,
        image_url=payload.image_url,
        likes_count=0,
        moderation_status=moderation_result["status"],
        moderation_reason=moderation_result["reason"],
        moderation_flags=",".join(moderation_result["flags"]),
        is_hidden=is_hidden,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    ModerationService.create_log(
        db,
        comment_id=comment.id,
        source="auto",
        action="create_comment",
        result=moderation_result["status"],
        flags=moderation_result["flags"],
        reason=moderation_result["reason"],
    )

    RankingService.refresh_topic_and_rankings(db, topic_id)

    if moderation_result["status"] == "pending_review":
        return {
            "status": "pending_review",
            "message": "Your comment is awaiting moderation and will appear once reviewed.",
            "comment": comment,
        }

    return {
        "status": "approved",
        "message": "Comment published",
        "comment": comment,
    }


@app.patch("/api/comments/{comment_id}", response_model=CommentOut)
def update_comment(
    comment_id: int, payload: CommentUpdate, db: Session = Depends(get_db)
):
    comment = get_comment_or_404(db, comment_id)

    if payload.text is not None:
        comment.text = payload.text
    comment.image_url = payload.image_url
    comment.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(comment)
    return comment


@app.delete("/api/comments/{comment_id}")
def delete_comment(comment_id: int, db: Session = Depends(get_db)):
    comment = get_comment_or_404(db, comment_id)
    topic_id = comment.topic_id
    db.delete(comment)
    db.commit()
    RankingService.refresh_topic_and_rankings(db, topic_id)
    return {"ok": True}


@app.post("/api/comments/{comment_id}/like")
def like_comment(
    comment_id: int, payload: CommentLikeRequest, db: Session = Depends(get_db)
):
    comment = get_comment_or_404(db, comment_id)
    like = CommentLike(comment_id=comment_id, user_identifier=payload.user_identifier)
    db.add(like)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Comment already liked by this user"
        )

    comment.likes_count = (
        db.query(CommentLike).filter(CommentLike.comment_id == comment_id).count()
    )
    db.commit()
    db.refresh(comment)
    RankingService.refresh_topic_and_rankings(db, comment.topic_id)
    return {"ok": True, "comment_id": comment_id, "likes_count": comment.likes_count}


@app.delete("/api/comments/{comment_id}/like")
def unlike_comment(
    comment_id: int,
    user_identifier: str = Query(..., min_length=2),
    db: Session = Depends(get_db),
):
    comment = get_comment_or_404(db, comment_id)
    like = (
        db.query(CommentLike)
        .filter(
            CommentLike.comment_id == comment_id,
            CommentLike.user_identifier == user_identifier,
        )
        .first()
    )
    if like:
        db.delete(like)
        db.commit()

    comment.likes_count = (
        db.query(CommentLike).filter(CommentLike.comment_id == comment_id).count()
    )
    db.commit()
    db.refresh(comment)
    RankingService.refresh_topic_and_rankings(db, comment.topic_id)
    return {"ok": True, "comment_id": comment_id, "likes_count": comment.likes_count}


@app.post("/api/comments/{comment_id}/report", response_model=ReportOut)
def report_comment(
    comment_id: int, payload: ReportCreate, db: Session = Depends(get_db)
):
    get_comment_or_404(db, comment_id)
    report = Report(
        comment_id=comment_id,
        reporter_identifier=payload.reporter_identifier,
        reason=payload.reason,
        details=payload.details,
        status="open",
    )
    db.add(report)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="This reporter already reported this comment"
        )

    db.refresh(report)

    # Immediately move comment to pending_review so it appears in the admin queue
    comment = get_comment_or_404(db, comment_id)
    if comment.moderation_status == "approved":
        comment.moderation_status = "pending_review"
        comment.is_hidden = True
        comment.moderation_reason = "Flagged by user report, pending admin review."
        comment.updated_at = datetime.now(timezone.utc)
        db.commit()
        ModerationService.create_log(
            db,
            comment_id=comment.id,
            source="auto",
            action="flagged_by_report",
            result="pending_review",
            flags=["user_report"],
            reason=comment.moderation_reason,
        )
        RankingService.refresh_topic_and_rankings(db, comment.topic_id)

    return report


@app.get(
    "/api/admin/reports",
    response_model=list[ReportOut],
    dependencies=[Depends(require_admin)],
)
def list_reports(status: str = Query(default="open"), db: Session = Depends(get_db)):
    reports = (
        db.query(Report)
        .filter(Report.status == status)
        .order_by(Report.created_at.desc())
        .all()
    )
    return reports


@app.get(
    "/api/admin/moderation/queue",
    response_model=list[ModerationQueueItem],
    dependencies=[Depends(require_admin)],
)
def moderation_queue(db: Session = Depends(get_db)):
    """
    Only return comments pending review.
    Approved/rejected comments move to processed list.
    """
    queue_items = (
        db.query(Comment, Topic.title)
        .join(Topic, Comment.topic_id == Topic.id)
        .filter(Comment.moderation_status == "pending_review")
        .order_by(Comment.created_at.desc())
        .all()
    )
    return [
        {
            **comment.__dict__,
            "topic_title": title,
        }
        for comment, title in queue_items
    ]


@app.get(
    "/api/admin/moderation/processed",
    response_model=list[ModerationQueueItem],
    dependencies=[Depends(require_admin)],
)
def moderation_processed(db: Session = Depends(get_db)):
    """
    Recently approved/rejected comments for review rollback.
    Shows last 50 processed items, including rejected comments regardless of hidden status.
    """
    processed_items = (
        db.query(Comment, Topic.title)
        .join(Topic, Comment.topic_id == Topic.id)
        .filter(Comment.moderation_status.in_(["approved", "rejected"]))
        .order_by(Comment.updated_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            **comment.__dict__,
            "topic_title": title,
        }
        for comment, title in processed_items
    ]


@app.post(
    "/api/admin/comments/{comment_id}/reopen",
    response_model=CommentOut,
    dependencies=[Depends(require_admin)],
)
def reopen_comment(comment_id: int, db: Session = Depends(get_db)):
    """
    Put a comment back into pending review queue for re-moderation.
    """
    comment = get_comment_or_404(db, comment_id)
    comment.moderation_status = "pending_review"
    comment.is_hidden = False
    comment.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(comment)

    ModerationService.create_log(
        db,
        comment_id=comment.id,
        source="admin",
        action="reopen",
        result="pending_review",
        flags=["manual_action"],
        reason="Reopened for re-review",
    )

    RankingService.refresh_topic_and_rankings(db, comment.topic_id)
    return comment


@app.patch(
    "/api/admin/comments/{comment_id}",
    response_model=CommentOut,
    dependencies=[Depends(require_admin)],
)
def admin_moderate_comment(
    comment_id: int,
    payload: AdminCommentActionRequest,
    db: Session = Depends(get_db),
):
    comment = get_comment_or_404(db, comment_id)

    if payload.action == "approve":
        comment.moderation_status = "approved"
        comment.is_hidden = False
    elif payload.action == "reject":
        comment.moderation_status = "rejected"
        comment.is_hidden = True
    elif payload.action == "hide":
        comment.is_hidden = True
    elif payload.action == "restore":
        comment.is_hidden = False

    comment.moderation_reason = payload.reason or comment.moderation_reason
    comment.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(comment)

    ModerationService.create_log(
        db,
        comment_id=comment.id,
        source="admin",
        action=payload.action,
        result=comment.moderation_status,
        flags=["manual_action"],
        reason=payload.reason,
    )

    RankingService.refresh_topic_and_rankings(db, comment.topic_id)
    return comment


@app.get(
    "/api/admin/moderation/logs",
    response_model=list[ModerationLogOut],
    dependencies=[Depends(require_admin)],
)
def moderation_logs(db: Session = Depends(get_db)):
    logs = (
        db.query(ModerationLog)
        .order_by(ModerationLog.created_at.desc())
        .limit(200)
        .all()
    )
    return logs
