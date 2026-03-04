from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.request import Request, urlopen

from .base_source import BaseSourceAdapter, RawArticle


class HackerNewsSourceAdapter(BaseSourceAdapter):
    source_name = "HackerNews"
    _TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
    _ITEM_URL_TEMPLATE = "https://hacker-news.firebaseio.com/v0/item/{item_id}.json"

    def fetch_top_items(self, limit: int) -> list[RawArticle]:
        try:
            request = Request(
                self._TOP_STORIES_URL,
                headers={"User-Agent": "AI-Builder-Daily/1.0"},
            )
            with urlopen(request, timeout=8) as response:
                top_ids = json.loads(response.read().decode("utf-8"))

            articles: list[RawArticle] = []
            for item_id in top_ids[: limit * 4]:
                if len(articles) >= limit:
                    break
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
                articles.append(
                    RawArticle(
                        title=item.get("title", "Untitled"),
                        url=item.get(
                            "url",
                            f"https://news.ycombinator.com/item?id={item.get('id')}",
                        ),
                        source=self.source_name,
                        score=int(item.get("score") or 0),
                        author=item.get("by"),
                        published_time=published_time,
                        summary=None,
                    )
                )

            return articles if articles else self._fallback_articles(limit)
        except Exception:
            return self._fallback_articles(limit)
