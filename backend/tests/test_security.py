from dataclasses import replace
from datetime import datetime, timezone
from io import BytesIO
import secrets

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app import main
from app.database import Base, get_db
from app.models import Comment, CommentLike, Topic, TopicLike
from app.security import COOKIE_NAME, MAX_BODY_BYTES, RequestSecurityMiddleware, SecuritySettings, verify_visitor
from app.services.moderation_service import ModerationService
from app.services.source_adapters.base_source import read_response
from app.services.source_adapters.rss_source import RSSSourceAdapter


@pytest.fixture
def api(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    topic = Topic(title="Security test", date_key=datetime.now(timezone.utc).date().isoformat())
    session.add(topic)
    session.flush()
    comment = Comment(topic_id=topic.id, user_identifier="owner", author_name="Owner", text="Original text", moderation_status="approved", is_hidden=False)
    session.add(comment)
    session.commit()
    monkeypatch.setattr(ModerationService, "_check_toxicity", staticmethod(lambda text: (0.0, [])))
    settings = replace(main.security_settings, admin_token=secrets.token_hex(32), session_secret=secrets.token_hex(32), anonymous_interactions=True, production=False)
    app = main.app
    monkeypatch.setattr(app.state, "security", settings)
    monkeypatch.setattr(app, "middleware_stack", None)
    for middleware in app.user_middleware:
        if middleware.cls is RequestSecurityMiddleware:
            monkeypatch.setitem(middleware.kwargs, "settings", settings)
        if middleware.cls is TrustedHostMiddleware:
            monkeypatch.setitem(middleware.kwargs, "allowed_hosts", ["testserver", "localhost", "127.0.0.1"])
    monkeypatch.setitem(app.dependency_overrides, get_db, lambda: session)
    client = TestClient(app)
    client.get(f"/api/topics/{topic.id}")
    yield client, session, topic.id, comment.id, settings
    client.close()
    session.close()
    engine.dispose()


@pytest.mark.parametrize("method,path,payload", [
    ("patch", "/api/comments/{comment}", {"text": "Attacker edit"}),
    ("delete", "/api/comments/{comment}", None),
    ("post", "/api/feed/realtime/refresh?force=true", None),
    ("post", "/api/admin/topics/enrich", None),
    ("get", "/api/admin/moderation/queue", None),
    ("post", "/api/admin/comments/{comment}/reopen", None),
])
def test_privileged_routes_reject_anonymous_requests(api, method, path, payload):
    client, session, _, comment_id, _ = api
    response = client.request(method, path.format(comment=comment_id), json=payload)
    assert response.status_code == 401
    assert session.get(Comment, comment_id).text == "Original text"


def test_public_default_token_does_not_work(api):
    client, _, _, _, _ = api
    assert client.get("/api/admin/moderation/queue", headers={"X-ADMIN-TOKEN": "dev-admin-token"}).status_code == 401


def test_missing_admin_configuration_disables_access(api):
    client, _, _, _, settings = api
    client.app.state.security = replace(settings, admin_token="")
    assert client.get("/api/admin/moderation/queue").status_code == 503


def test_comment_edits_are_hidden_until_review(api):
    client, session, topic_id, comment_id, settings = api
    response = client.patch(f"/api/comments/{comment_id}", json={"text": "Changed content"}, headers={"X-ADMIN-TOKEN": settings.admin_token})
    assert response.status_code == 200
    assert response.json()["is_hidden"] is True
    assert response.json()["moderation_status"] == "pending_review"
    assert client.get(f"/api/topics/{topic_id}/comments").json()["items"] == []
    assert client.get(f"/api/topics/{topic_id}/comments/highlights").json() == []
    assert session.get(Comment, comment_id).text == "Changed content"


def test_pending_content_never_appears_in_highlights(api):
    client, session, topic_id, comment_id, _ = api
    comment = session.get(Comment, comment_id)
    comment.moderation_status = "pending_review"
    comment.is_hidden = False  # Even legacy inconsistent records must be filtered.
    session.commit()
    assert client.get(f"/api/topics/{topic_id}/comments/highlights").json() == []


def test_report_requests_review_without_hiding_content(api):
    client, session, topic_id, comment_id, settings = api
    response = client.post(f"/api/comments/{comment_id}/report", json={"reason": "other", "reporter_identifier": "spoofed-user"})
    assert response.status_code == 200
    assert response.json()["reporter_identifier"] != "spoofed-user"
    assert session.get(Comment, comment_id).is_hidden is False
    assert client.get(f"/api/topics/{topic_id}/comments").json()["items"]
    queue = client.get("/api/admin/moderation/queue", headers={"X-ADMIN-TOKEN": settings.admin_token}).json()
    assert [c["id"] for c in queue] == [comment_id]
    assert client.post(f"/api/comments/{comment_id}/report", json={"reason": "other", "reporter_identifier": "another-spoof"}).status_code == 409
    client.patch(f"/api/admin/comments/{comment_id}", json={"action": "approve"}, headers={"X-ADMIN-TOKEN": settings.admin_token})
    assert client.get("/api/admin/moderation/queue", headers={"X-ADMIN-TOKEN": settings.admin_token}).json() == []


def test_body_identifiers_cannot_impersonate_another_visitor(api):
    client, session, topic_id, comment_id, settings = api
    visitor_id = verify_visitor(client.cookies.get(COOKIE_NAME), settings.session_secret)
    assert client.post(f"/api/topics/{topic_id}/like", json={"user_identifier": "victim"}).status_code == 200
    assert session.query(TopicLike).one().user_identifier == visitor_id
    assert client.post(f"/api/topics/{topic_id}/like", json={"user_identifier": "rotated-id"}).status_code == 409
    assert client.post(f"/api/comments/{comment_id}/like", json={"user_identifier": "victim"}).status_code == 200
    assert session.query(CommentLike).one().user_identifier == visitor_id


def test_unlike_cannot_remove_someone_elses_vote(api):
    client, session, topic_id, comment_id, _ = api
    session.add(TopicLike(topic_id=topic_id, user_identifier="victim"))
    session.add(CommentLike(comment_id=comment_id, user_identifier="victim"))
    session.commit()
    client.delete(f"/api/topics/{topic_id}/like?user_identifier=victim")
    client.delete(f"/api/comments/{comment_id}/like?user_identifier=victim")
    assert session.query(TopicLike).filter_by(user_identifier="victim").count() == 1
    assert session.query(CommentLike).filter_by(user_identifier="victim").count() == 1


def test_tampered_or_missing_cookie_cannot_write(api):
    client, _, topic_id, _, _ = api
    client.cookies.clear()
    client.cookies.set(COOKIE_NAME, "a" * 32 + "." + "b" * 64)
    assert client.post(f"/api/topics/{topic_id}/like", json={}).status_code == 401
    client.cookies.clear()
    assert client.post(f"/api/topics/{topic_id}/like", json={}).status_code == 401


def test_anonymous_writes_can_be_disabled(api):
    client, _, topic_id, _, settings = api
    client.app.state.security = replace(settings, anonymous_interactions=False)
    assert client.post(f"/api/topics/{topic_id}/like", json={}).status_code == 403


def test_cookie_is_httponly_and_signed(api):
    client, _, topic_id, _, settings = api
    client.cookies.clear()
    response = client.get(f"/api/topics/{topic_id}")
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    assert verify_visitor(client.cookies.get(COOKIE_NAME), settings.session_secret)
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"


def test_production_cookies_are_secure(api):
    _, _, _, _, settings = api
    app = FastAPI()
    app.state.security = replace(settings, production=True)
    app.add_middleware(RequestSecurityMiddleware, settings=app.state.security)

    @app.get("/api/example")
    def example():
        return {"ok": True}

    with TestClient(app, base_url="https://hub.example.com") as client:
        response = client.get("/api/example")
        assert "secure" in response.headers["set-cookie"].lower()
        assert response.headers["strict-transport-security"] == "max-age=31536000"


def test_unknown_hosts_are_rejected(api):
    client, _, _, _, _ = api
    assert client.get("/api/topics/history", headers={"Host": "attacker.example"}).status_code == 400


def test_unknown_origins_cannot_read_credentialed_responses(api):
    client, _, topic_id, _, _ = api
    response = client.get(f"/api/topics/{topic_id}", headers={"Origin": "https://attacker.example"})
    assert "access-control-allow-origin" not in response.headers


def test_unauthorized_rebuilds_do_not_spend_admin_rate_budget(api, monkeypatch):
    client, _, _, _, settings = api
    for _ in range(6):
        assert client.post("/api/feed/realtime/refresh").status_code == 401
    monkeypatch.setattr(main.SignalTopicSyncService, "sync_from_recent_hourly_feed", lambda *a, **k: {})
    response = client.post("/api/admin/topics/enrich", headers={"X-ADMIN-TOKEN": settings.admin_token})
    assert response.status_code == 200


def test_cross_origin_writes_are_blocked(api):
    client, _, topic_id, _, _ = api
    assert client.post(f"/api/topics/{topic_id}/like", json={}, headers={"Origin": "https://attacker.example"}).status_code == 403


@pytest.mark.parametrize("streamed", [False, True])
def test_request_size_limit_includes_streaming_bodies(api, streamed):
    client, _, topic_id, _, _ = api
    body = b"a" * (MAX_BODY_BYTES + 1)
    response = client.post(f"/api/topics/{topic_id}/comments", content=iter([body[:8000], body[8000:]]) if streamed else body)
    assert response.status_code == 413


def test_request_rate_limit_cannot_be_bypassed_with_body_ids(api):
    client, _, topic_id, _, _ = api
    for index in range(30):
        client.post(f"/api/topics/{topic_id}/like", json={"user_identifier": f"user-{index}"})
    response = client.post(f"/api/topics/{topic_id}/like", json={})
    assert response.status_code == 429 and response.headers["retry-after"] == "60"


def test_read_routes_do_not_trigger_collection_or_ai(api, monkeypatch):
    client, _, topic_id, _, _ = api

    def unexpected(*args, **kwargs):
        pytest.fail("A public GET triggered collection, AI enrichment, or database pruning")

    monkeypatch.setattr(main.SignalTopicSyncService, "sync_from_recent_hourly_feed", unexpected)
    monkeypatch.setattr(main.HourlyFeedService, "get_or_create_current_feed", unexpected)
    monkeypatch.setattr(main.HourlyFeedService, "generate_hourly_feed", unexpected)
    monkeypatch.setattr(main.HourlyFeedService, "prune_invalid_batches", unexpected)
    for path in ["/api/topics/daily-top-signals", "/api/feed/stream", "/api/feed/history", f"/api/topics/{topic_id}"]:
        assert client.get(path).status_code == 200
    assert client.get("/api/feed/realtime").status_code == 404


@pytest.mark.parametrize("url", ["javascript:alert(1)", "data:image/svg+xml,<svg/>", "file:///etc/passwd", "https://user:password@example.com/image.png"])
def test_unsafe_attachment_urls_are_rejected(api, url):
    client, _, topic_id, _, _ = api
    assert client.post(f"/api/topics/{topic_id}/comments", json={"author_name": "Guest", "text": "Content", "image_url": url}).status_code == 422


def test_model_unavailability_keeps_comment_pending(api, monkeypatch):
    client, session, topic_id, _, _ = api
    monkeypatch.setattr(ModerationService, "_check_toxicity", staticmethod(lambda text: (0.0, ["moderation_unavailable"])))
    response = client.post(f"/api/topics/{topic_id}/comments", json={"author_name": "Guest", "text": "Unchecked content"})
    assert response.status_code == 200
    assert response.json()["status"] == "pending_review"
    assert response.json()["comment"]["is_hidden"] is True


def test_image_attachments_need_manual_review(api):
    client, _, topic_id, _, _ = api
    response = client.post(f"/api/topics/{topic_id}/comments", json={"author_name": "Guest", "text": "Image", "image_url": "https://example.com/photo.png"})
    assert response.json()["status"] == "pending_review"
    assert response.json()["comment"]["is_hidden"] is True


def test_source_responses_have_a_memory_bound():
    with pytest.raises(ValueError):
        read_response(BytesIO(b"x" * 101), limit=100)


def test_rss_external_entities_are_not_expanded(monkeypatch):
    xml = b'<!DOCTYPE rss [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><rss><channel><item><title>&xxe;</title></item></channel></rss>'
    monkeypatch.setattr("app.services.source_adapters.rss_source.urlopen", lambda *a, **k: BytesIO(xml))
    articles = RSSSourceAdapter("Test RSS", "https://example.com/feed").fetch_top_items(1)
    assert articles[0].is_fallback is True


def test_security_defaults_and_production_configuration(monkeypatch):
    for name in ["ADMIN_TOKEN", "SESSION_SECRET", "ALLOW_ANONYMOUS_INTERACTIONS", "APP_ENV", "CORS_ORIGINS", "ALLOWED_HOSTS"]:
        monkeypatch.delenv(name, raising=False)
    settings = SecuritySettings.from_env()
    assert not settings.admin_token and not settings.anonymous_interactions
    monkeypatch.setenv("ADMIN_TOKEN", "dev-admin-token")
    with pytest.raises(ValueError):
        SecuritySettings.from_env()
    monkeypatch.delenv("ADMIN_TOKEN")
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(ValueError):
        SecuritySettings.from_env()
    monkeypatch.setenv("CORS_ORIGINS", "https://hub.example.com")
    monkeypatch.setenv("ALLOWED_HOSTS", "hub.example.com")
    monkeypatch.setenv("ALLOW_ANONYMOUS_INTERACTIONS", "true")
    with pytest.raises(ValueError):
        SecuritySettings.from_env()
    monkeypatch.setenv("SESSION_SECRET", secrets.token_hex(32))
    assert SecuritySettings.from_env().production
