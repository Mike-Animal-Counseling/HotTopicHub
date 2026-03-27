from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import models
from app.database import SessionLocal, ensure_sqlite_schema, engine
from app.services.hourly_feed_service import HourlyFeedService
from app.services.ranking_service import RankingService
from app.services.signal_topic_sync_service import SignalTopicSyncService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reset dynamic HotTopicHub data and backfill recent hourly feed windows.",
    )
    parser.add_argument(
        "--backfill-hours",
        type=int,
        default=48,
        help="Number of completed hourly windows to rebuild. Default: 48.",
    )
    return parser.parse_args()


def reset_dynamic_data(db) -> None:
    db.query(models.CommentLike).delete(synchronize_session=False)
    db.query(models.Report).delete(synchronize_session=False)
    db.query(models.ModerationLog).delete(synchronize_session=False)
    db.query(models.Comment).delete(synchronize_session=False)
    db.query(models.TopicLike).delete(synchronize_session=False)
    db.query(models.Topic).delete(synchronize_session=False)
    db.query(models.HourlyFeedItem).delete(synchronize_session=False)
    db.query(models.HourlyFeedBatch).delete(synchronize_session=False)
    db.commit()


def stamp_batch_to_hour(db, batch_id: int, hour_end: datetime) -> None:
    (
        db.query(models.HourlyFeedBatch)
        .filter(models.HourlyFeedBatch.id == batch_id)
        .update(
            {
                models.HourlyFeedBatch.created_at: hour_end,
            },
            synchronize_session=False,
        )
    )
    (
        db.query(models.HourlyFeedItem)
        .filter(models.HourlyFeedItem.batch_id == batch_id)
        .update(
            {
                models.HourlyFeedItem.created_at: hour_end,
            },
            synchronize_session=False,
        )
    )
    db.commit()


def backfill_recent_hours(db, backfill_hours: int) -> dict[str, int]:
    if backfill_hours <= 0:
        return {"batches": 0, "topics": 0}

    current_hour = datetime.now(timezone.utc).replace(
        minute=0,
        second=0,
        microsecond=0,
    )
    start_hour = current_hour - timedelta(hours=backfill_hours - 1)

    batches_created = 0
    for offset in range(backfill_hours):
        hour_end = start_hour + timedelta(hours=offset)
        batch = HourlyFeedService.generate_hourly_feed(
            db,
            hour_key=hour_end.isoformat(),
            force=True,
        )
        stamp_batch_to_hour(db, batch.id, hour_end)
        SignalTopicSyncService.sync_from_recent_hourly_feed(db, now=hour_end)
        batches_created += 1
        print(f"[backfill] {hour_end.isoformat()} -> batch {batch.id}")

    date_keys = [
        row[0]
        for row in db.query(models.Topic.date_key)
        .filter(models.Topic.is_active.is_(True))
        .distinct()
        .all()
    ]
    for date_key in sorted(date_keys):
        RankingService.recompute_rankings(db, date_key)

    topics_count = (
        db.query(models.Topic).filter(models.Topic.is_active.is_(True)).count()
    )
    return {"batches": batches_created, "topics": topics_count}


def main() -> None:
    args = parse_args()
    models.Base.metadata.create_all(bind=engine)
    ensure_sqlite_schema()
    db = SessionLocal()
    try:
        print("[reset] clearing dynamic data")
        reset_dynamic_data(db)
        print(f"[backfill] rebuilding last {args.backfill_hours} hours")
        stats = backfill_recent_hours(db, args.backfill_hours)
        print(
            f"[done] rebuilt {stats['batches']} hourly batches and {stats['topics']} active topics"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
