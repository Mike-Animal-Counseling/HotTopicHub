from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.request import Request, urlopen

from .base_source import BaseSourceAdapter, RawArticle


class RSSSourceAdapter(BaseSourceAdapter):
    def __init__(self, source_name: str, feed_url: str):
        self.source_name = source_name
        self.feed_url = feed_url

    def fetch_top_items(self, limit: int) -> list[RawArticle]:
        try:
            request = Request(
                self.feed_url,
                headers={"User-Agent": "AI-Builder-Daily/1.0"},
            )
            with urlopen(request, timeout=8) as response:
                xml_data = response.read()

            root = ET.fromstring(xml_data)
            items = []

            channel_items = root.findall("./channel/item")
            if channel_items:
                for entry in channel_items[:limit]:
                    published = self._parse_pub_date(self._text(entry.find("pubDate")))
                    items.append(
                        RawArticle(
                            title=self._text(entry.find("title"), "Untitled"),
                            url=self._text(entry.find("link"), "https://example.com"),
                            source=self.source_name,
                            score=50,
                            author=self._text(entry.find("author")),
                            summary=self._text(entry.find("description")),
                            published_time=published,
                        )
                    )
            else:
                atom_entries = root.findall("{http://www.w3.org/2005/Atom}entry")
                for entry in atom_entries[:limit]:
                    link_node = entry.find("{http://www.w3.org/2005/Atom}link")
                    href = (
                        link_node.attrib.get("href")
                        if link_node is not None
                        else "https://example.com"
                    )
                    published_text = self._text(
                        entry.find("{http://www.w3.org/2005/Atom}published")
                    ) or self._text(entry.find("{http://www.w3.org/2005/Atom}updated"))
                    items.append(
                        RawArticle(
                            title=self._text(
                                entry.find("{http://www.w3.org/2005/Atom}title"),
                                "Untitled",
                            ),
                            url=href,
                            source=self.source_name,
                            score=50,
                            author=self._text(
                                entry.find(
                                    "{http://www.w3.org/2005/Atom}author/{http://www.w3.org/2005/Atom}name"
                                )
                            ),
                            summary=self._text(
                                entry.find("{http://www.w3.org/2005/Atom}summary")
                            ),
                            published_time=self._parse_pub_date(published_text),
                        )
                    )

            return items if items else self._fallback_articles(limit)
        except Exception:
            return self._fallback_articles(limit)

    @staticmethod
    def _text(node, default: str | None = None) -> str | None:
        if node is None or node.text is None:
            return default
        return node.text.strip()

    @staticmethod
    def _parse_pub_date(value: str | None) -> datetime:
        if not value:
            return datetime.now(timezone.utc)
        try:
            parsed = parsedate_to_datetime(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            try:
                parsed_iso = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if parsed_iso.tzinfo is None:
                    parsed_iso = parsed_iso.replace(tzinfo=timezone.utc)
                return parsed_iso.astimezone(timezone.utc)
            except Exception:
                return datetime.now(timezone.utc)
