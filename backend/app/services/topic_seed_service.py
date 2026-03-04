from datetime import date

from sqlalchemy.orm import Session

from app.services.ranking_service import RankingService
from app.services.topic_pipeline_service import TopicPipelineService


class TopicSeedService:
    @staticmethod
    def seed_daily_topics(db: Session, date_key: str | None = None) -> int:
        normalized_date = date_key or date.today().isoformat()
        seeded_count = TopicPipelineService.generate_daily_topics(
            db,
            date_key=normalized_date,
            per_source_limit=4,
            top_k=10,
        )
        if seeded_count == 0:
            return 0
        RankingService.recompute_rankings(db, normalized_date)
        return seeded_count
