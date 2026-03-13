from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "sqlite:///./hot_topic_hub.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def ensure_sqlite_schema():
    schema_updates = {
        "hourly_feed_batches": {
            "window_start": (
                "ALTER TABLE hourly_feed_batches "
                "ADD COLUMN window_start TEXT DEFAULT '1970-01-01T00:00:00+00:00'"
            ),
            "window_end": (
                "ALTER TABLE hourly_feed_batches "
                "ADD COLUMN window_end TEXT DEFAULT '1970-01-01T00:00:00+00:00'"
            ),
            "created_at": (
                "ALTER TABLE hourly_feed_batches "
                "ADD COLUMN created_at TEXT DEFAULT '1970-01-01T00:00:00+00:00'"
            ),
        },
        "hourly_feed_items": {
            "summary": "ALTER TABLE hourly_feed_items ADD COLUMN summary TEXT",
            "canonical_url": "ALTER TABLE hourly_feed_items ADD COLUMN canonical_url TEXT",
            "source_url": "ALTER TABLE hourly_feed_items ADD COLUMN source_url TEXT",
            "sources_json": "ALTER TABLE hourly_feed_items ADD COLUMN sources_json TEXT",
            "published_time": "ALTER TABLE hourly_feed_items ADD COLUMN published_time TEXT",
            "content_type": (
                "ALTER TABLE hourly_feed_items "
                "ADD COLUMN content_type TEXT DEFAULT 'other'"
            ),
            "builder_score": (
                "ALTER TABLE hourly_feed_items ADD COLUMN builder_score FLOAT DEFAULT 0"
            ),
            "event_score": (
                "ALTER TABLE hourly_feed_items ADD COLUMN event_score FLOAT DEFAULT 0"
            ),
            "newsworthiness_score": (
                "ALTER TABLE hourly_feed_items "
                "ADD COLUMN newsworthiness_score FLOAT DEFAULT 0"
            ),
            "feed_score": (
                "ALTER TABLE hourly_feed_items ADD COLUMN feed_score FLOAT DEFAULT 0"
            ),
            "created_at": (
                "ALTER TABLE hourly_feed_items "
                "ADD COLUMN created_at TEXT DEFAULT '1970-01-01T00:00:00+00:00'"
            ),
        },
        "topics": {
            "source_clicks_count": (
                "ALTER TABLE topics ADD COLUMN source_clicks_count INTEGER DEFAULT 0"
            ),
            "primary_source": "ALTER TABLE topics ADD COLUMN primary_source TEXT",
        },
    }

    with engine.begin() as connection:
        for table_name, column_updates in schema_updates.items():
            table_exists = connection.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name = :table_name"
                ),
                {"table_name": table_name},
            ).first()
            if not table_exists:
                continue

            existing_columns = {
                row[1]
                for row in connection.execute(text(f"PRAGMA table_info({table_name})"))
            }
            for column_name, ddl in column_updates.items():
                if column_name in existing_columns:
                    continue
                connection.execute(text(ddl))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
