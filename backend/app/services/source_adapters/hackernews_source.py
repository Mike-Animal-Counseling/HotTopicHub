from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen

from .base_source import BaseSourceAdapter, RawArticle


class HackerNewsSourceAdapter(BaseSourceAdapter):
    source_name = "HackerNews"
    _TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
    _BEST_STORIES_URL = "https://hacker-news.firebaseio.com/v0/beststories.json"
    _NEW_STORIES_URL = "https://hacker-news.firebaseio.com/v0/newstories.json"
    _ITEM_URL_TEMPLATE = "https://hacker-news.firebaseio.com/v0/item/{item_id}.json"

    def fetch_top_items(
        self,
        limit: int,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
    ) -> list[RawArticle]:
        window_end = window_end or datetime.now(timezone.utc)
        window_start = window_start or (window_end - timedelta(hours=24))
        now = window_end
        try:
            request = Request(
                self._TOP_STORIES_URL,
                headers={"User-Agent": "AI-Builder-Daily/1.0"},
            )
            with urlopen(request, timeout=8) as response:
                top_ids = json.loads(response.read().decode("utf-8"))

            best_request = Request(
                self._BEST_STORIES_URL,
                headers={"User-Agent": "AI-Builder-Daily/1.0"},
            )
            with urlopen(best_request, timeout=8) as response:
                best_ids = json.loads(response.read().decode("utf-8"))

            new_request = Request(
                self._NEW_STORIES_URL,
                headers={"User-Agent": "AI-Builder-Daily/1.0"},
            )
            with urlopen(new_request, timeout=8) as response:
                new_ids = json.loads(response.read().decode("utf-8"))

            candidate_ids: list[int] = []
            seen_ids: set[int] = set()
            for item_id in [*top_ids[: limit * 4], *best_ids[: limit * 3], *new_ids[: limit * 6]]:
                if item_id in seen_ids:
                    continue
                seen_ids.add(item_id)
                candidate_ids.append(item_id)

            articles: list[RawArticle] = []
            for item_id in candidate_ids:
                item_url = self._ITEM_URL_TEMPLATE.format(item_id=item_id)
                item_request = Request(
                    item_url,
                    headers={"User-Agent": "AI-Builder-Daily/1.0"},
                )
                with urlopen(item_request, timeout=8) as item_response:
                    item = json.loads(item_response.read().decode("utf-8"))

                if not item or item.get("type") != "story" or not item.get("title"):
                    continue

                unix_time = item.get("time")
                published_time = datetime.fromtimestamp(unix_time, tz=timezone.utc)
                if published_time < window_start or published_time >= window_end:
                    continue
                score = int(item.get("score") or 0)
                descendants = int(item.get("descendants") or 0)
                age_hours = max((now - published_time).total_seconds() / 3600, 1.0)
                articles.append(
                    RawArticle(
                        title=item.get("title", "Untitled"),
                        url=item.get(
                            "url",
                            f"https://news.ycombinator.com/item?id={item.get('id')}",
                        ),
                        source=self.source_name,
                        score=score,
                        author=item.get("by"),
                        published_time=published_time,
                        summary=None,
                        engagement_count=score + descendants,
                        likes=score,
                        comments=descendants,
                        trend_score=(score + descendants * 1.5) / age_hours,
                        top10_eligible=(score >= 40 or descendants >= 20),
                    )
                )

            articles.sort(key=lambda article: article.trend_score, reverse=True)
            articles = articles[:limit]
            return articles if articles else self._fallback_articles(limit)
        except Exception:
            return self._fallback_articles(limit)
