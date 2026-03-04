from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.parse import quote
from urllib.request import Request, urlopen

from .base_source import BaseSourceAdapter, RawArticle


class GitHubTrendingSourceAdapter(BaseSourceAdapter):
    source_name = "GitHub"

    def fetch_top_items(self, limit: int) -> list[RawArticle]:
        query = quote("ai OR llm OR agent OR rag OR startup")
        url = (
            "https://api.github.com/search/repositories"
            f"?q={query}&sort=stars&order=desc&per_page={max(limit, 1)}"
        )

        try:
            request = Request(
                url,
                headers={
                    "User-Agent": "AI-Builder-Daily/1.0",
                    "Accept": "application/vnd.github+json",
                },
            )
            with urlopen(request, timeout=8) as response:
                payload = json.loads(response.read().decode("utf-8"))

            items = payload.get("items", [])
            articles: list[RawArticle] = []
            for repo in items[:limit]:
                updated_at = (
                    repo.get("updated_at") or datetime.now(timezone.utc).isoformat()
                )
                published = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                title = f"{repo.get('full_name', 'unknown/repo')} trending on GitHub"
                articles.append(
                    RawArticle(
                        title=title,
                        url=repo.get("html_url", "https://github.com"),
                        source=self.source_name,
                        score=int(repo.get("stargazers_count") or 0),
                        author=(repo.get("owner") or {}).get("login"),
                        summary=repo.get("description"),
                        published_time=published,
                    )
                )

            return articles if articles else self._fallback_articles(limit)
        except Exception:
            return self._fallback_articles(limit)
