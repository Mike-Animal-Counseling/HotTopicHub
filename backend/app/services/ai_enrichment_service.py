from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from urllib import error, request

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AIEnrichmentConfig:
    api_key: str
    model: str
    api_url: str
    timeout_seconds: float
    enabled: bool


class AIEnrichmentService:
    DEFAULT_MODEL = "deepseek/deepseek-chat"
    DEFAULT_API_URL = "https://openrouter.ai/api/v1/chat/completions"

    @staticmethod
    def get_config() -> AIEnrichmentConfig:
        api_key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
        model = (
            os.getenv("OPENROUTER_MODEL")
            or os.getenv("OPENROUTER_TEXT_MODEL")
            or AIEnrichmentService.DEFAULT_MODEL
        ).strip()
        api_url = (
            os.getenv("OPENROUTER_CHAT_COMPLETIONS_URL")
            or AIEnrichmentService.DEFAULT_API_URL
        ).strip()
        try:
            timeout_seconds = float(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "20"))
        except ValueError:
            timeout_seconds = 20.0
        enabled = (os.getenv("AI_ENRICHMENT_ENABLED", "true") or "true").lower() not in {
            "0",
            "false",
            "no",
        }
        return AIEnrichmentConfig(
            api_key=api_key,
            model=model,
            api_url=api_url,
            timeout_seconds=timeout_seconds,
            enabled=enabled and bool(api_key),
        )

    @staticmethod
    def is_enabled() -> bool:
        return AIEnrichmentService.get_config().enabled

    @staticmethod
    def build_enrichment(item) -> dict[str, str] | None:
        config = AIEnrichmentService.get_config()
        if not config.enabled:
            return None

        payload = {
            "model": config.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an editor for an English-language AI builder news product. "
                        "Return only valid JSON with four string fields: summary, key_insights, "
                        "why_it_matters, technical_summary. Keep it factual, concise, and avoid hype. "
                        "Do not mention that you are an AI. Do not use markdown."
                    ),
                },
                {
                    "role": "user",
                    "content": AIEnrichmentService._build_prompt(item),
                },
            ],
            "temperature": 0.2,
            "max_tokens": 280,
        }

        raw_response = AIEnrichmentService._post_json(
            url=config.api_url,
            api_key=config.api_key,
            timeout_seconds=config.timeout_seconds,
            payload=payload,
        )
        parsed = AIEnrichmentService._parse_chat_completion(raw_response)
        if parsed is None:
            logger.warning("AI enrichment response could not be parsed for item: %s", item.title)
        return parsed

    @staticmethod
    def _build_prompt(item) -> str:
        sources = ", ".join(item.sources[:4]) if getattr(item, "sources", None) else "Unknown"
        summary = (item.summary or "").strip()
        return (
            "Create English editorial copy for a topic card and detail page.\n"
            "Requirements:\n"
            "- summary: 1 sentence, max 30 words.\n"
            "- key_insights: 1-2 sentences, max 55 words.\n"
            "- why_it_matters: 1-2 sentences, max 55 words.\n"
            "- technical_summary: 1-2 sentences, max 65 words.\n"
            "- Focus on what is known from the input only.\n"
            "- If the input is thin, be cautious and specific about uncertainty.\n"
            "- Output JSON only.\n\n"
            f"Title: {item.title}\n"
            f"Source list: {sources}\n"
            f"Primary source URL: {item.source_url or 'Unknown'}\n"
            f"Canonical URL: {item.canonical_url or 'Unknown'}\n"
            f"Content type: {item.content_type}\n"
            f"Builder score: {item.builder_score:.2f}\n"
            f"Event score: {item.event_score:.2f}\n"
            f"Newsworthiness score: {item.newsworthiness_score:.2f}\n"
            f"Existing source summary: {summary or 'None'}\n"
        )

    @staticmethod
    def _post_json(
        *,
        url: str,
        api_key: str,
        timeout_seconds: float,
        payload: dict,
    ) -> dict | None:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url=url,
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:5173",
                "X-Title": "HotTopicHub",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="ignore")
            logger.warning("OpenRouter enrichment HTTP %s: %s", exc.code, error_body[:400])
        except Exception as exc:
            logger.warning("OpenRouter enrichment request failed: %s", exc)
        return None

    @staticmethod
    def _parse_chat_completion(payload: dict | None) -> dict[str, str] | None:
        if not payload:
            return None
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return None
        message = choices[0].get("message") or {}
        content = message.get("content")
        text = AIEnrichmentService._extract_text_content(content)
        if not text:
            return None
        return AIEnrichmentService._parse_json_block(text)

    @staticmethod
    def _extract_text_content(content) -> str | None:
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text" and isinstance(block.get("text"), str):
                    parts.append(block["text"])
            merged = "".join(parts).strip()
            return merged or None
        return None

    @staticmethod
    def _parse_json_block(text: str) -> dict[str, str] | None:
        candidate = text.strip()
        if candidate.startswith("```"):
            lines = candidate.splitlines()
            if len(lines) >= 3:
                candidate = "\n".join(lines[1:-1]).strip()
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            start = candidate.find("{")
            end = candidate.rfind("}")
            if start < 0 or end <= start:
                return None
            try:
                payload = json.loads(candidate[start : end + 1])
            except json.JSONDecodeError:
                return None
        required_fields = (
            "summary",
            "key_insights",
            "why_it_matters",
            "technical_summary",
        )
        parsed: dict[str, str] = {}
        for field in required_fields:
            value = payload.get(field)
            if not isinstance(value, str):
                return None
            cleaned = " ".join(value.split()).strip()
            if not cleaned:
                return None
            parsed[field] = cleaned
        return parsed
