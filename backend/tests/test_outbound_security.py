from io import BytesIO
from urllib import error, request

import pytest

from app.services.ai_enrichment_service import AIEnrichmentService
from app.services.http_client import NoRedirects, open_https
from app.services.moderation_service import ModerationService


@pytest.mark.parametrize("url", ["file:///etc/passwd", "http://example.com", "https://localhost/data", "https://127.0.0.1/data", "https://169.254.169.254/latest/meta-data", "https://[::1]/data", "https://user:pass@example.com/api"])
def test_unsafe_outbound_destinations_are_rejected(url):
    with pytest.raises(ValueError):
        open_https(url)


def test_redirects_cannot_forward_authorization_to_another_host():
    req = request.Request("https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": "Bearer test-placeholder"})
    with pytest.raises(error.URLError):
        NoRedirects().redirect_request(req, None, 307, "Redirect", {}, "https://attacker.example/")


def test_ai_error_body_is_not_logged(monkeypatch, caplog):
    def fail(*args, **kwargs):
        raise error.HTTPError("https://openrouter.ai", 400, "Failure", {}, BytesIO(b"sensitive submitted content"))
    monkeypatch.setattr("app.services.ai_enrichment_service.open_https", fail)
    assert AIEnrichmentService._post_json(url="https://openrouter.ai", api_key="test-placeholder", timeout_seconds=1, payload={}) is None
    assert "sensitive submitted content" not in caplog.text
    assert "HTTP 400" in caplog.text


def test_nonfinite_model_result_does_not_approve_content(monkeypatch):
    class InvalidModel:
        def predict(self, text):
            return {"toxicity": float("nan")}
    monkeypatch.setattr(ModerationService, "_get_detoxify_model", staticmethod(lambda: InvalidModel()))
    assert "moderation_unavailable" in ModerationService._check_toxicity("Content")[1]


def test_model_downloads_are_disabled_by_default(monkeypatch):
    monkeypatch.delenv("MODERATION_MODEL_ENABLED", raising=False)
    assert ModerationService._get_detoxify_model() is None
