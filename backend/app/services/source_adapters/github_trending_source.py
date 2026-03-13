from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from urllib.request import Request, urlopen

from .base_source import BaseSourceAdapter, RawArticle


class GitHubTrendingSourceAdapter(BaseSourceAdapter):
    source_name = "GitHub"

    def fetch_top_items(
        self,
        limit: int,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
    ) -> list[RawArticle]:
        window_end = window_end or datetime.now(timezone.utc)
        window_start = window_start or (window_end - timedelta(hours=24))
        now = window_end
        created_cutoff = (now - timedelta(days=30)).date().isoformat()
        pushed_cutoff = (now - timedelta(days=7)).date().isoformat()
        query = quote(
            "ai OR llm OR agent OR rag OR openai OR anthropic "
            f"created:>={created_cutoff} pushed:>={pushed_cutoff}"
        )
        url = (
            "https://api.github.com/search/repositories"
            f"?q={query}&sort=updated&order=desc&per_page={max(limit * 5, limit)}"
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
            for rank, repo in enumerate(items, start=1):
                updated_at = repo.get("updated_at") or now.isoformat()
                published = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                created_at = repo.get("created_at") or updated_at
                created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                age_days = max((now - created).total_seconds() / 86400, 1.0)
                stargazers = int(repo.get("stargazers_count") or 0)
                forks = int(repo.get("forks_count") or 0)
                approx_daily_growth = stargazers / age_days
                trend_score = approx_daily_growth + (forks * 0.3)
                title = f"{repo.get('full_name', 'unknown/repo')} trending on GitHub"
                article = RawArticle(
                    title=title,
                    url=repo.get("html_url", "https://github.com"),
                    source=self.source_name,
                    score=stargazers,
                    author=(repo.get("owner") or {}).get("login"),
                    summary=repo.get("description"),
                    published_time=published,
                    engagement_count=stargazers + forks,
                    stars=stargazers,
                    shares=forks,
                    trend_score=trend_score,
                    source_rank=rank,
                    top10_eligible=(
                        approx_daily_growth >= 40
                        and age_days <= 45
                        and window_start <= published < window_end
                    ),
                )
                if article.top10_eligible or approx_daily_growth >= 15:
                    articles.append(article)
                if len(articles) >= limit:
                    break

            return articles if articles else self._fallback_articles(limit)
        except Exception:
            return self._fallback_articles(limit)
