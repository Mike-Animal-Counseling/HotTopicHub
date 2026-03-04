from __future__ import annotations

import math
import re

from app.models import Comment


class CommentRankingService:
    @staticmethod
    def _estimate_reply_count(comment: Comment) -> int:
        text = comment.text or ""
        return len(re.findall(r"@\w+", text))

    @staticmethod
    def _contains_links(comment: Comment) -> bool:
        text = comment.text or ""
        return "http://" in text or "https://" in text

    @staticmethod
    def compute_comment_score(comment: Comment) -> float:
        likes = max(comment.likes_count or 0, 0)
        reply_count = CommentRankingService._estimate_reply_count(comment)
        text_length = len((comment.text or "").strip())
        link_bonus = 0.4 if CommentRankingService._contains_links(comment) else 0.0

        return (
            1.8 * math.log1p(likes)
            + 1.2 * math.log1p(reply_count)
            + 0.6 * math.log1p(text_length)
            + link_bonus
        )

    @staticmethod
    def rank_comments(comments: list[Comment]) -> list[dict]:
        ranked = sorted(
            comments,
            key=lambda comment: CommentRankingService.compute_comment_score(comment),
            reverse=True,
        )

        labels = ["Top Insight", "Top Resource", "Top Technical Comment"]
        output: list[dict] = []
        for index, comment in enumerate(ranked):
            label = labels[index] if index < len(labels) else None
            output.append(
                {
                    "comment": comment,
                    "score": round(
                        CommentRankingService.compute_comment_score(comment), 3
                    ),
                    "highlight": label,
                }
            )
        return output
