from __future__ import annotations

from app.services.pipeline_types import TopicCluster


class AISummaryService:
    @staticmethod
    def generate_topic_summary(cluster: TopicCluster) -> dict[str, str]:
        source_list = ", ".join(cluster.sources) or "multiple sources"
        primary_titles = "; ".join(article.title for article in cluster.articles[:3])

        key_insights = (
            f"{len(cluster.articles)} related reports were merged from {source_list}. "
            f"Main coverage: {primary_titles}."
        )
        why_it_matters = (
            "This topic signals momentum for AI builders and startups and may impact "
            "developer tooling, product strategy, or model adoption."
        )
        technical_summary = (
            "Placeholder summary generated without external LLM API. "
            "Enable an LLM provider to produce deeper architecture and benchmark analysis."
        )

        return {
            "summary": key_insights,
            "key_insights": key_insights,
            "why_it_matters": why_it_matters,
            "technical_summary": technical_summary,
        }
