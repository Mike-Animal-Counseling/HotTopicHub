import re
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import Comment, ModerationLog, Report


class ModerationService:
    LOW_RISK_PROFANITY = {"idiot", "stupid", "dumb"}
    MEDIUM_HATE = {"hate", "harass", "racist", "sexist"}
    HIGH_SEXUAL_VIOLENCE_SELF_HARM = {
        "kill myself",
        "suicide",
        "bomb",
        "shoot",
        "rape",
        "murder",
    }

    SHORTENER_DOMAINS = {"bit.ly", "tinyurl.com", "t.co"}
    SUSPICIOUS_TLDS = {".xyz", ".top", ".click", ".work", ".zip"}

    @staticmethod
    def extract_links(text: str) -> list[str]:
        if not text:
            return []
        return re.findall(r"https?://[^\s]+", text)

    @staticmethod
    def image_moderation_hook(image_url: str | None) -> tuple[list[str], str | None]:
        if not image_url:
            return [], None
        return [], None

    @staticmethod
    def _normalize_text(text: str) -> str:
        return re.sub(r"\s+", " ", text.strip().lower())

    @staticmethod
    def run_text_rules(
        db: Session, topic_id: int, user_identifier: str, text: str
    ) -> dict:
        normalized = ModerationService._normalize_text(text)
        flags: list[str] = []

        for bad_word in ModerationService.HIGH_SEXUAL_VIOLENCE_SELF_HARM:
            if bad_word in normalized:
                flags.append("high_risk_content")
                return {
                    "status": "rejected",
                    "flags": sorted(set(flags)),
                    "reason": "High-risk content detected.",
                }

        if any(word in normalized for word in ModerationService.MEDIUM_HATE):
            flags.append("hate_or_harassment")

        if any(word in normalized for word in ModerationService.LOW_RISK_PROFANITY):
            flags.append("profanity")

        links = ModerationService.extract_links(text)
        if len(links) > 2:
            flags.append("too_many_external_links")

        if any(domain in normalized for domain in ModerationService.SHORTENER_DOMAINS):
            flags.append("shortener_link")

        if any(
            normalized.endswith(tld) or tld in normalized
            for tld in ModerationService.SUSPICIOUS_TLDS
        ):
            flags.append("suspicious_tld")

        now = datetime.now(timezone.utc)
        since_30s = now - timedelta(seconds=30)
        since_5m = now - timedelta(minutes=5)

        comments_last_30s = (
            db.query(Comment)
            .filter(
                Comment.user_identifier == user_identifier,
                Comment.created_at >= since_30s,
            )
            .count()
        )
        if comments_last_30s >= 1:
            flags.append("rate_limit_30_seconds")

        comments_last_5m = (
            db.query(Comment)
            .filter(
                Comment.user_identifier == user_identifier,
                Comment.created_at >= since_5m,
            )
            .count()
        )
        if comments_last_5m >= 5:
            flags.append("rate_limit_5_minutes")

        repeated_text_count = (
            db.query(Comment)
            .filter(
                Comment.topic_id == topic_id,
                Comment.user_identifier == user_identifier,
                Comment.text == text,
                Comment.created_at >= since_5m,
            )
            .count()
        )
        if repeated_text_count > 0:
            flags.append("duplicate_text_short_window")

        if "rate_limit_30_seconds" in flags or "rate_limit_5_minutes" in flags:
            return {
                "status": "rejected",
                "flags": sorted(set(flags)),
                "reason": "Comment posting frequency limit exceeded.",
            }

        if "duplicate_text_short_window" in flags:
            return {
                "status": "pending_review",
                "flags": sorted(set(flags)),
                "reason": "Duplicate text detected in a short time window.",
            }

        if (
            "hate_or_harassment" in flags
            or "too_many_external_links" in flags
            or "suspicious_tld" in flags
        ):
            return {
                "status": "pending_review",
                "flags": sorted(set(flags)),
                "reason": "Content requires moderator review.",
            }

        return {
            "status": "approved",
            "flags": sorted(set(flags)),
            "reason": "Passed automatic moderation.",
        }

    @staticmethod
    def run_auto_moderation(
        db: Session,
        topic_id: int,
        user_identifier: str,
        text: str,
        image_url: str | None,
    ) -> dict:
        text_result = ModerationService.run_text_rules(
            db, topic_id, user_identifier, text
        )
        image_flags, image_reason = ModerationService.image_moderation_hook(image_url)

        flags = list(text_result["flags"]) + image_flags
        reason = text_result["reason"]
        if image_reason:
            reason = f"{reason} {image_reason}".strip()

        return {
            "status": text_result["status"],
            "flags": sorted(set(flags)),
            "reason": reason,
        }

    @staticmethod
    def create_log(
        db: Session,
        *,
        comment_id: int | None,
        source: str,
        action: str,
        result: str,
        flags: list[str] | None,
        reason: str | None,
    ) -> ModerationLog:
        log = ModerationLog(
            comment_id=comment_id,
            source=source,
            action=action,
            result=result,
            flags=",".join(flags) if flags else None,
            reason=reason,
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log


class ReportService:
    AUTO_HIDE_THRESHOLD = 3

    @staticmethod
    def evaluate_auto_hide(db: Session, comment_id: int) -> bool:
        open_reports_count = (
            db.query(Report)
            .filter(Report.comment_id == comment_id, Report.status == "open")
            .count()
        )
        if open_reports_count < ReportService.AUTO_HIDE_THRESHOLD:
            return False

        comment = db.query(Comment).filter(Comment.id == comment_id).first()
        if not comment:
            return False

        comment.is_hidden = True
        comment.moderation_status = "pending_review"
        comment.moderation_reason = (
            "Automatically hidden after report threshold reached."
        )
        db.commit()

        ModerationService.create_log(
            db,
            comment_id=comment.id,
            source="auto",
            action="auto_hide_due_to_reports",
            result="pending_review",
            flags=["report_threshold_reached"],
            reason=comment.moderation_reason,
        )
        return True
