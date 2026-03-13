from .base_source import BaseSourceAdapter, RawArticle
from .github_trending_source import GitHubTrendingSourceAdapter
from .hackernews_source import HackerNewsSourceAdapter
from .producthunt_source import ProductHuntSourceAdapter
from .reddit_source import RedditSourceAdapter
from .rss_source import RSSSourceAdapter

__all__ = [
    "BaseSourceAdapter",
    "RawArticle",
    "HackerNewsSourceAdapter",
    "GitHubTrendingSourceAdapter",
    "ProductHuntSourceAdapter",
    "RedditSourceAdapter",
    "RSSSourceAdapter",
]
