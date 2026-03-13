from __future__ import annotations

import html
import re


class TopicEnrichmentService:
    @staticmethod
    def _clean_text(value: str | None, max_length: int = 320) -> str | None:
        if not value:
            return None
        normalized = html.unescape(value)
        normalized = re.sub(r"<[^>]+>", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        if not normalized:
            return None
        if len(normalized) <= max_length:
            return normalized
        trimmed = normalized[: max_length - 1].rstrip(" ,;:.")
        return f"{trimmed}..."

    @staticmethod
    def _content_label(content_type: str) -> str:
        return (content_type or "signal").replace("_", " ")

    @staticmethod
    def build_from_feed_item(item) -> dict[str, str | None]:
        sources = item.sources or []
        primary_source = sources[0] if sources else "the live feed"
        content_label = TopicEnrichmentService._content_label(item.content_type)
        source_text = ", ".join(sources[:3]) if sources else primary_source
        cleaned_summary = TopicEnrichmentService._clean_text(item.summary)

        summary = cleaned_summary or (
            f"{item.title} is surfacing in the hourly feed as a {content_label} signal "
            f"from {primary_source} with strong builder relevance."
        )

        key_insights = (
            f"Surfaced from {source_text}. This item is currently classified as {content_label} "
            f"with builder fit {item.builder_score:.1f} and event strength {item.event_score:.1f}."
        )

        why_it_matters = (
            f"This is active enough to enter the live discussion queue now. If the community keeps "
            f"liking, commenting on, or clicking through it, the topic can move into the Daily Top Signals "
            f"ranking for the past 24 hours."
        )

        if item.content_type == "repo":
            technical_summary = (
                "Repository-led signal. Check implementation quality, setup friction, dependency choices, "
                "and whether the project exposes reusable code or APIs for builders."
            )
        elif item.content_type == "research":
            technical_summary = (
                "Research-led signal. Review benchmarks, evaluation setup, inference constraints, and whether "
                "there is code, a reproducible method, or an adoption path for product teams."
            )
        elif item.content_type in {"tool", "platform_update"}:
            technical_summary = (
                "Tooling-led signal. Focus on API surface, SDK ergonomics, integration effort, pricing or "
                "deployment constraints, and what it changes for production AI workflows."
            )
        elif item.content_type == "launch":
            technical_summary = (
                "Launch-led signal. Validate what is actually shipping now, who can use it today, and whether "
                "it changes shipping velocity for builders rather than just generating announcement noise."
            )
        elif item.content_type == "discussion":
            technical_summary = (
                "Discussion-led signal. The value here is usually in implementation lessons, tradeoffs, and "
                "community feedback rather than a brand-new artifact."
            )
        else:
            technical_summary = (
                "Builder-relevant signal from the live feed. Review the original source to confirm implementation "
                "details, release maturity, and practical usefulness."
            )

        return {
            "summary": summary,
            "key_insights": key_insights,
            "why_it_matters": why_it_matters,
            "technical_summary": technical_summary,
        }
