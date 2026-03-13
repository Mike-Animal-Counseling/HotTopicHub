from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen

from .base_source import BaseSourceAdapter, RawArticle


class RedditSourceAdapter(BaseSourceAdapter):
    source_name = "Reddit"

    def __init__(self, subreddits: list[str] | None = None):
        self.subreddits = subreddits or [
            "LocalLLaMA",
            "MachineLearning",
            "OpenAI",
            "singularity",
        ]

    def fetch_top_items(
        self,
        limit: int,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
    ) -> list[RawArticle]:
        subreddit_expr = "+".join(self.subreddits)
        url = (
            f"https://www.reddit.com/r/{subreddit_expr}/hot.json"
            f"?limit={max(limit * 4, limit)}&raw_json=1"
        )
        window_end = window_end or datetime.now(timezone.utc)
        window_start = window_start or (window_end - timedelta(hours=24))
        now = window_end

        try:
            request = Request(
                url,
                headers={
                    "User-Agent": "AI-Builder-Daily/1.0",
                    "Accept": "application/json",
                },
            )
            with urlopen(request, timeout=8) as response:
                payload = json.loads(response.read().decode("utf-8"))

            items = payload.get("data", {}).get("children", [])
            articles: list[RawArticle] = []
            for rank, entry in enumerate(items, start=1):
                data = entry.get("data", {})
                title = data.get("title")
                permalink = data.get("permalink")
                created_utc = data.get("created_utc")
                if not title or not permalink or not created_utc:
                    continue

                published_time = datetime.fromtimestamp(created_utc, tz=timezone.utc)
                if published_time < window_start or published_time >= window_end:
                    continue

                ups = int(data.get("ups") or data.get("score") or 0)
                comments = int(data.get("num_comments") or 0)
                age_hours = max((now - published_time).total_seconds() / 3600, 1.0)
                trend_score = (ups + comments * 1.5) / age_hours
                article_url = f"https://www.reddit.com{permalink}"

                articles.append(
                    RawArticle(
                        title=title,
                        url=article_url,
                        source=self.source_name,
                        score=ups,
                        author=data.get("author"),
                        summary=data.get("selftext") or None,
                        published_time=published_time,
                        engagement_count=ups + comments,
                        likes=ups,
                        comments=comments,
                        trend_score=trend_score,
                        source_rank=rank,
                        top10_eligible=(ups >= 30 or comments >= 10),
                    )
                )

                if len(articles) >= limit:
                    break

            return articles if articles else self._fallback_articles(limit)
        except Exception:
            return self._fallback_articles(limit)
