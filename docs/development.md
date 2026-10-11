# Developer guide

[← Back to README](../README.md)

HotTopicHub separates external source collection from community ranking. External sources supply the live discovery feed; activity inside the platform determines the Daily Top 10.

## Data flow

### Live Feed

1. Fetch articles from source adapters.
2. Score articles for AI-builder relevance.
3. Cluster related items using title similarity, semantic similarity, and token overlap.
4. Select a diverse hourly batch and save `HourlyFeedBatch` and `HourlyFeedItem` records.
5. Compose recent non-empty batches into a deduplicated, continuous stream.

The frontend supports manual refresh, passive new-item detection, and incremental loading. **Refresh Feed** reloads the cached stream for visitors; admins can also rebuild the current hourly batch. Topic titles open their discussion pages. Public GET routes read stored data without initiating collection or enrichment.

### Topic sync and enrichment

1. Read recent `HourlyFeedItem` records.
2. Match an existing `Topic` or create a new one.
3. Attach a summary, key insights, why it matters, and a technical summary.

OpenRouter can generate the editorial fields. When AI enrichment is unavailable, deterministic templates provide fallback copy. Admins can rebuild enrichment for recent topics.

### Daily Top 10 and history

1. Read recent active topics from the last 24 hours.
2. Rank them using likes, comments, source clicks, and a recency boost.
3. Apply a per-source cap and return the top results.

Daily History uses `Topic.date_key` to browse past signal sets. Topic detail pages preserve navigation context so readers can return to the feed, daily list, or history.

## Backend API

For request parameters and response schemas, use [FastAPI's interactive documentation](http://127.0.0.1:8000/docs) while the backend is running.

### Topics

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/api/topics/daily-top-signals` | Daily Top 10 |
| `GET` | `/api/topics/history` | Available history dates |
| `GET` | `/api/topics/history/{date_key}` | Signals for a date |
| `GET` | `/api/topics/{topic_id}` | Topic details |
| `POST`, `DELETE` | `/api/topics/{topic_id}/like` | Add or remove a topic like |
| `POST` | `/api/topics/{topic_id}/source-click` | Record a source click |
| `GET`, `POST` | `/api/topics/{topic_id}/comments` | List or create comments |
| `GET` | `/api/topics/{topic_id}/comments/highlights` | Ranked comment highlights |

### Comments

| Method | Route | Purpose |
| --- | --- | --- |
| `PATCH`, `DELETE` | `/api/comments/{comment_id}` | Edit or delete a comment |
| `POST`, `DELETE` | `/api/comments/{comment_id}/like` | Add or remove a comment like |
| `POST` | `/api/comments/{comment_id}/report` | Report a comment |

Editing and deletion require `X-ADMIN-TOKEN`; edits return to hidden, pending review. Reports request admin review and cannot automatically hide published content.

### Feed

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/api/feed/realtime` | Read an hourly feed |
| `GET` | `/api/feed/stream` | Read the continuous feed |
| `POST` | `/api/feed/realtime/refresh` | Refresh an hourly batch |
| `GET` | `/api/feed/history` | List hourly batches |

Feed refresh requires `X-ADMIN-TOKEN`. Anonymous comments, likes, reports, and source clicks require `ALLOW_ANONYMOUS_INTERACTIONS=true` and a valid signed visitor cookie issued on an API GET. Payload identifiers never grant ownership or identity.

### Admin

All admin routes require an `X-ADMIN-TOKEN` header matching `ADMIN_TOKEN`. The frontend's Admin page accepts this token for the review tools.

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/api/admin/moderation/queue` | Pending moderation items |
| `GET` | `/api/admin/moderation/processed` | Processed moderation items |
| `GET` | `/api/admin/moderation/logs` | Moderation activity |
| `GET` | `/api/admin/reports` | Comment reports |
| `PATCH` | `/api/admin/comments/{comment_id}` | Review a comment |
| `POST` | `/api/admin/comments/{comment_id}/reopen` | Reopen a comment for review |
| `POST` | `/api/admin/topics/enrich` | Rebuild topic enrichment |

## Main files

| Responsibility | File |
| --- | --- |
| API and application lifecycle | [`backend/app/main.py`](../backend/app/main.py) |
| Database setup | [`backend/app/database.py`](../backend/app/database.py) |
| Source collection | [`source_collection_service.py`](../backend/app/services/source_collection_service.py) |
| Hourly feed generation | [`hourly_feed_service.py`](../backend/app/services/hourly_feed_service.py) |
| Topic sync | [`signal_topic_sync_service.py`](../backend/app/services/signal_topic_sync_service.py) |
| Topic enrichment | [`topic_enrichment_service.py`](../backend/app/services/topic_enrichment_service.py) |
| OpenRouter integration | [`ai_enrichment_service.py`](../backend/app/services/ai_enrichment_service.py) |
| Daily ranking | [`daily_top_signals_service.py`](../backend/app/services/daily_top_signals_service.py) |
| Frontend routes | [`frontend/src/App.jsx`](../frontend/src/App.jsx) |
| Frontend API client | [`frontend/src/api.js`](../frontend/src/api.js) |

## Local development notes

- Start the backend from `backend/`; the relative SQLite path creates `backend/hot_topic_hub.db`.
- The frontend uses same-origin `/api` requests. Vite proxies them to `http://127.0.0.1:8000`, preserving visitor cookies. `VITE_API_BASE_URL` can override the API origin; never put secrets in a `VITE_` variable.
- Startup refreshes the hourly feed and syncs topics. A background task refreshes the feed at hourly boundaries. Optional Detoxify preloading requires `MODERATION_MODEL_ENABLED=true`; model failure keeps comments pending instead of approving unchecked content.
- `OPENROUTER_TIMEOUT_SECONDS` controls the AI request timeout and defaults to `20`.
- See [CONTRIBUTING.md](../CONTRIBUTING.md) for regression tests, audits, and lockfile updates, and [SECURITY.md](../SECURITY.md) for deployment constraints.
