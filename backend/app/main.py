import logging
import os
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

from .database import engine, get_db
from . import models
from .models import (
    Comment,
    CommentLike,
    DailyTopicBatch,
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
    DailyTopicBatchListResponse,
    DailyTopicBatchOut,
    ModerationLogOut,
    ModerationQueueItem,
    RankedCommentOut,
    ReportCreate,
    ReportOut,
    SeedDailyResponse,
    TopicLikeRequest,
    TopicListResponse,
    TopicOut,
)
from .services.moderation_service import ModerationService, ReportService
from .services.comment_ranking_service import CommentRankingService
from .services.ranking_service import RankingService
from .services.topic_seed_service import TopicSeedService

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dev-admin-token")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        logger.info("=== Application startup ===")
        models.Base.metadata.create_all(bind=engine)
        db_gen = get_db()
        db = next(db_gen)
        logger.info("Triggering daily topic pipeline...")
        TopicSeedService.seed_daily_topics(db, date.today().isoformat())
        logger.info("Preloading Detoxify model for comment moderation...")
        ModerationService._get_detoxify_model()
        logger.info("Detoxify model loaded successfully")
        logger.info("=== Application startup complete ===")
    except Exception as e:
        logger.error(f"Startup error: {e}", exc_info=True)
    finally:
        db_gen.close()

    yield


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


def normalize_date_key(date_value: str | None) -> str:
    if not date_value:
        return date.today().isoformat()
    try:
        return date.fromisoformat(date_value).isoformat()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD") from exc


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


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/topics", response_model=TopicListResponse)
def list_topics(
    date_key: str | None = Query(default=None, alias="date"),
    db: Session = Depends(get_db),
):
    normalized_date = normalize_date_key(date_key)
    items = (
        db.query(Topic)
        .filter(Topic.date_key == normalized_date, Topic.is_active.is_(True))
        .order_by(Topic.daily_rank.asc(), Topic.score.desc())
        .all()
    )
    return {"items": items}


@app.get("/api/topics/trending", response_model=TopicListResponse)
def list_trending_topics(
    date_key: str | None = Query(default=None, alias="date"),
    db: Session = Depends(get_db),
):
    normalized_date = normalize_date_key(date_key)
    items = (
        db.query(Topic)
        .filter(Topic.date_key == normalized_date, Topic.is_active.is_(True))
        .order_by(Topic.daily_rank.asc(), Topic.score.desc())
        .limit(10)
        .all()
    )
    return {"items": items}


@app.get("/api/topics/history", response_model=DailyTopicBatchListResponse)
def list_topic_history(db: Session = Depends(get_db)):
    batches = db.query(DailyTopicBatch).order_by(DailyTopicBatch.date.desc()).all()
    items = [
        DailyTopicBatchOut(
            id=batch.id,
            date=batch.date,
            created_at=batch.created_at,
            topics_count=len(batch.topics),
        )
        for batch in batches
    ]
    return {"items": items}


@app.get("/api/topics/{topic_id}", response_model=TopicOut)
def get_topic(topic_id: int, db: Session = Depends(get_db)):
    return get_topic_or_404(db, topic_id)


@app.post("/api/topics/seed-daily", response_model=SeedDailyResponse)
def seed_daily_topics(
    date_key: str | None = Query(default=None, alias="date"),
    db: Session = Depends(get_db),
):
    normalized_date = normalize_date_key(date_key)
    seeded_count = TopicSeedService.seed_daily_topics(db, normalized_date)
    return {"date_key": normalized_date, "seeded_count": seeded_count}


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
