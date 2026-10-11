"""Safe defaults for the demo API; anonymous visitors are not verified accounts."""

import hashlib
import hmac
import os
import re
import secrets
import time
from collections import OrderedDict, deque
from dataclasses import dataclass
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from starlette.responses import JSONResponse


COOKIE_NAME = "hottopichub_visitor"
MAX_BODY_BYTES = 16 * 1024


@dataclass(frozen=True)
class SecuritySettings:
    admin_token: str
    session_secret: str
    anonymous_interactions: bool
    production: bool
    allowed_origins: tuple[str, ...]
    allowed_hosts: tuple[str, ...]

    @classmethod
    def from_env(cls):
        environment = os.getenv("APP_ENV", "development")
        if environment not in {"development", "production", "test"}:
            raise ValueError("APP_ENV must be development, production, or test.")
        production = environment == "production"
        admin_token = os.getenv("ADMIN_TOKEN", "").strip()
        session_secret = os.getenv("SESSION_SECRET", "").strip()
        anonymous = os.getenv("ALLOW_ANONYMOUS_INTERACTIONS", "false").lower() == "true"
        origins = tuple(filter(None, (o.strip() for o in os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(","))))
        hosts = tuple(filter(None, (h.strip() for h in os.getenv(
            "ALLOWED_HOSTS", "localhost,127.0.0.1,testserver"
        ).split(","))))
        if admin_token and not 32 <= len(admin_token) <= 256:
            raise ValueError("ADMIN_TOKEN must contain at least 32 characters; leave it empty to disable admin access.")
        if session_secret and len(session_secret) < 32:
            raise ValueError("SESSION_SECRET must contain at least 32 characters.")
        if not origins or any("*" in o or urlsplit(o).scheme not in {"http", "https"} or not urlsplit(o).netloc or urlsplit(o).path or urlsplit(o).query or urlsplit(o).fragment or urlsplit(o).username for o in origins):
            raise ValueError("CORS_ORIGINS must contain explicit HTTP(S) origins without paths or wildcards.")
        if not hosts or any("*" in host for host in hosts):
            raise ValueError("ALLOWED_HOSTS must contain explicit host names.")
        if production:
            if any(urlsplit(o).scheme != "https" for o in origins):
                raise ValueError("Production CORS_ORIGINS must use HTTPS.")
            if anonymous and not session_secret:
                raise ValueError("Production anonymous interactions require a persistent SESSION_SECRET.")
            if not os.getenv("ALLOWED_HOSTS"):
                raise ValueError("Set ALLOWED_HOSTS explicitly in production.")
        return cls(admin_token, session_secret or secrets.token_hex(32), anonymous, production, origins, hosts)


def sign_visitor(visitor_id: str, secret: str) -> str:
    signature = hmac.new(secret.encode(), visitor_id.encode(), hashlib.sha256).hexdigest()
    return f"{visitor_id}.{signature}"


def verify_visitor(cookie: str, secret: str) -> str | None:
    if not re.fullmatch(r"[0-9a-f]{32}\.[0-9a-f]{64}", cookie):
        return None
    visitor_id = cookie.split(".", 1)[0]
    return visitor_id if hmac.compare_digest(cookie, sign_visitor(visitor_id, secret)) else None


def require_admin(request: Request):
    token = request.app.state.security.admin_token
    if not token:
        raise HTTPException(status_code=503, detail="Admin access is disabled. Configure ADMIN_TOKEN on the server.")
    provided = request.headers.get("x-admin-token", "")
    if len(provided) > 256 or not secrets.compare_digest(provided.encode(), token.encode()):
        raise HTTPException(status_code=401, detail="Invalid admin token.")


def require_visitor(request: Request) -> str:
    settings = request.app.state.security
    if not settings.anonymous_interactions:
        raise HTTPException(status_code=403, detail="Anonymous interactions are disabled on this server.")
    visitor_id = verify_visitor(request.cookies.get(COOKIE_NAME, ""), settings.session_secret)
    if not visitor_id:
        raise HTTPException(status_code=401, detail="Reload the page before submitting an interaction.")
    return visitor_id


class RequestSecurityMiddleware:
    """Bound request memory and per-worker abuse state before parsing request data."""

    def __init__(self, app, settings: SecuritySettings):
        self.app = app
        self.settings = settings
        self.buckets = OrderedDict()

    def allow(self, key, limit, now):
        bucket = self.buckets.pop(key, deque())
        while bucket and bucket[0] <= now - 60:
            bucket.popleft()
        self.buckets[key] = bucket
        while len(self.buckets) > 10000:
            self.buckets.popitem(last=False)
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request = Request(scope)
        path = scope["path"]
        write = scope["method"] not in {"GET", "HEAD", "OPTIONS"}
        headers = [
            (b"x-content-type-options", b"nosniff"),
            (b"referrer-policy", b"no-referrer"),
            (b"x-frame-options", b"DENY"),
            (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
        ]
        if path.startswith("/api/"):
            headers.extend([(b"cache-control", b"no-store"), (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'; base-uri 'none'")])
        if self.settings.production and scope.get("scheme") == "https":
            headers.append((b"strict-transport-security", b"max-age=31536000"))
        cookie = None
        if scope["method"] == "GET" and path.startswith("/api/") and self.settings.anonymous_interactions and not verify_visitor(request.cookies.get(COOKIE_NAME, ""), self.settings.session_secret):
            cookie = JSONResponse({})
            cookie.set_cookie(COOKIE_NAME, sign_visitor(secrets.token_hex(16), self.settings.session_secret), httponly=True, secure=self.settings.production, samesite="lax", max_age=365 * 86400)

        async def secured_send(message):
            if message["type"] == "http.response.start":
                message["headers"] = list(message["headers"]) + headers
                if cookie is not None:
                    message["headers"].extend((k, v) for k, v in cookie.raw_headers if k == b"set-cookie")
            await send(message)

        async def reject(status, detail, extra=None):
            await JSONResponse({"detail": detail}, status_code=status, headers=extra)(scope, receive, secured_send)

        origin = request.headers.get("origin")
        if write and origin and origin not in self.settings.allowed_origins:
            return await reject(403, "Origin is not allowed.")
        client = (scope.get("client") or ("unknown",))[0]
        now = time.monotonic()
        if path.startswith("/api/") and not self.allow((client, "write" if write else "read"), 30 if write else 180, now):
            return await reject(429, "Too many requests. Try again in a minute.", {"Retry-After": "60"})
        if write and path in {"/api/feed/realtime/refresh", "/api/admin/topics/enrich"}:
            try:
                require_admin(request)
            except HTTPException as exc:
                return await reject(exc.status_code, exc.detail)
            if not self.allow(("global", "expensive"), 5, now):
                return await reject(429, "Rebuild limit reached. Try again in a minute.", {"Retry-After": "60"})
        declared = request.headers.get("content-length")
        if declared is not None:
            try:
                size = int(declared)
            except ValueError:
                return await reject(400, "Invalid Content-Length.")
            if size < 0:
                return await reject(400, "Invalid Content-Length.")
            if size > MAX_BODY_BYTES:
                return await reject(413, "Request body is too large.")
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > MAX_BODY_BYTES:
                return await reject(413, "Request body is too large.")
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, secured_send)
