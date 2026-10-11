# Security policy

## Reporting a vulnerability

Report security issues privately through [GitHub's vulnerability reporting form](https://github.com/Mike-Animal-Counseling/HotTopicHub/security/advisories/new). Include the affected commit, reproduction steps, impact, and a suggested fix if available. Do not put credentials, private data, or exploit details in a public issue.

Only the latest default-branch version receives security fixes. There are no supported stable releases yet.

## Security defaults

- Admin access is disabled until `ADMIN_TOKEN` is configured with at least 32 characters. There is no built-in admin password.
- Anonymous comments, likes, reports, and source-click tracking are disabled by default. Enable `ALLOW_ANONYMOUS_INTERACTIONS` only when intentionally running an interactive demo.
- Anonymous interactions use a signed, HttpOnly visitor cookie. Client-supplied identifiers are accepted for compatibility but never grant identity or permissions. These cookies identify a browser, not a verified person; clearing cookies can create a new visitor. Display names are unverified.
- Comment editing/deletion, forced feed collection, and AI rebuilds require the admin token. Edited or reopened comments remain hidden until approved again.
- Model failures and unreviewed images leave comments pending. Reporting a comment cannot automatically remove it; admins review reports and decide.
- Public reads do not trigger collection or AI calls. Request bodies are capped at 16 KiB. Per-worker limits allow 180 API reads and 30 writes per client IP per minute, plus 5 expensive rebuilds per minute across that worker.
- Outbound requests use HTTPS, reject literal private/local addresses, refuse redirects, and cap responses. Source destinations are controlled by server code/configuration. API error bodies are not logged.

## Running a public instance

The safe default is a read-only demonstration. Before exposing an instance:

1. Use `APP_ENV=production`, explicit `ALLOWED_HOSTS`, and HTTPS-only `CORS_ORIGINS`. Serve the frontend and `/api` on the same origin through a reverse proxy. The Vite server is for local development.
2. Generate independent random `ADMIN_TOKEN` and `SESSION_SECRET` values with `python -c "import secrets; print(secrets.token_hex(32))"`. Keep them in deployment secrets, never in Git or frontend build variables. Production interactive demos require a persistent session secret. Rotate it to invalidate visitor cookies; rotate the admin token if exposed.
3. Terminate TLS at the proxy and configure Uvicorn to trust forwarded headers only from that proxy. Block direct access to the backend port. Set a 16 KiB request-body limit, timeouts, and shared rate limiting at the edge. The in-process limiter is bounded but does not coordinate multiple workers or stop distributed attacks.
4. Restrict outbound network access to the configured source/API/model providers and block private/metadata networks at the infrastructure layer. Hostname resolution is handled by the system resolver; application checks do not provide complete DNS-rebinding protection.
5. Keep anonymous writes off for a production community until you add verified accounts, authorization, and stronger abuse controls. Do not treat a visitor cookie or display name as an authenticated account.
6. Install the optional moderation dependencies only if needed, then explicitly enable `MODERATION_MODEL_ENABLED`. Without a working model, admins must approve new comments. Embedding downloads require `EMBEDDING_MODEL_ENABLED=true` and a reviewed immutable 40-character `EMBEDDING_MODEL_REVISION`; remote model code and pickle model weights are disabled for embeddings.
7. Protect the SQLite database and backups. Serve only `frontend/dist`, never the repository root, `.env`, backend files, or model caches. Set frontend security headers at the proxy; the API sets its own restrictive headers.

See the [security review](docs/security-review.md) for the reviewed scope, fixes, validation, and remaining limitations.
