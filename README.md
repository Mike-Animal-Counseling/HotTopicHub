# AI Builder Daily Hub

AI Builder Daily Hub is a full-stack AI signal product with three core surfaces:

- `Live Feed`: an hourly stream of fresh AI-builder topics collected from external sources
- `Daily Top 10`: the strongest community-engaged topics from the last 24 hours inside the platform
- `Daily History`: archived daily signal sets, browsable by date

The system separates source collection from community ranking:

1. external sources feed the hourly stream
2. recent feed items are synced into interactive `Topic` records
3. users like, comment, and click through to sources
4. the platform ranks the last 24 hours of community signals into a daily top list

## Stack

- Backend: FastAPI, SQLAlchemy, SQLite
- Frontend: React, Vite, React Router

## Product Shape

### Live Feed

- Pulls from sources such as Hacker News, GitHub Trending, Product Hunt, Reddit, and selected RSS feeds
- Scores and clusters source items into hourly batches
- Works as the lightweight discovery surface
- Clicking a title opens the discussion thread for that topic

### Daily Top 10

- Built from platform interaction, not external source rank alone
- Ranking signals:
  - likes
  - comments
  - source clicks
  - recency boost
- Caps output so one source cannot dominate the list
- Shows richer editorial context:
  - summary
  - insight summary
  - why it matters

### Daily History

- Lets users revisit prior daily top lists by date
- Uses the current `Topic.date_key` model, not the old daily batch pipeline

### Topic Detail

- Full discussion page for a topic
- Shows:
  - summary
  - key insights
  - why it matters
  - technical summary
  - comments and ranked highlights
  - source link

### Moderation

- Topic comments
- Comment likes
- Comment reports
- Automatic moderation
- Admin review queue and processed review list

## Active Backend Routes

### Topics

- `GET /api/topics/daily-top-signals`
- `GET /api/topics/history`
- `GET /api/topics/history/{date_key}`
- `GET /api/topics/{id}`
- `POST /api/topics/{id}/like`
- `DELETE /api/topics/{id}/like`
- `POST /api/topics/{id}/source-click`
- `GET /api/topics/{id}/comments`
- `GET /api/topics/{id}/comments/highlights`
- `POST /api/topics/{id}/comments`

### Comments

- `PATCH /api/comments/{id}`
- `DELETE /api/comments/{id}`
- `POST /api/comments/{id}/like`
- `DELETE /api/comments/{id}/like`
- `POST /api/comments/{id}/report`

### Feed

- `GET /api/feed/realtime`
- `POST /api/feed/realtime/refresh`
- `GET /api/feed/history`

### Admin

Requires `X-ADMIN-TOKEN`.

- `GET /api/admin/moderation/queue`
- `GET /api/admin/moderation/processed`
- `GET /api/admin/moderation/logs`
- `GET /api/admin/reports`
- `PATCH /api/admin/comments/{id}`
- `POST /api/admin/comments/{id}/reopen`

## Current Backend Flow

### Live Feed

1. Fetch from source adapters
2. Score raw articles for builder relevance
3. Cluster related source items
4. Select a diverse hourly batch
5. Save `HourlyFeedBatch` and `HourlyFeedItem`

### Topic Sync

1. Read recent `HourlyFeedItem`
2. Match or create `Topic`
3. Attach enrichment fields:
   - summary
   - key insights
   - why it matters
   - technical summary

### Daily Top 10

1. Read recent active `Topic`
2. Compute engagement rank from platform activity
3. Apply per-source cap
4. Return top results for the last 24 hours

## Main Files

- Backend entrypoint: `backend/app/main.py`
- Source collection: `backend/app/services/source_collection_service.py`
- Hourly feed generation: `backend/app/services/hourly_feed_service.py`
- Topic sync from feed: `backend/app/services/signal_topic_sync_service.py`
- Topic enrichment: `backend/app/services/topic_enrichment_service.py`
- Daily ranking: `backend/app/services/daily_top_signals_service.py`

## Local Setup

### Backend

```powershell
cd .\backend\
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Notes:

- The app refreshes the hourly feed on startup
- Recent hourly items are synced into topics automatically
- Default admin token: `dev-admin-token`
- Active database: `backend/hot_topic_hub.db`

### Frontend

```powershell
cd .\frontend\
npm install
npm run dev
```

## Current Direction

- `Live Feed` is the lightweight discovery and discussion entry point
- `Daily Top 10` is the curated community signal page
- `Daily History` is the archive surface
- `Topic Detail` is the full reading and discussion surface

The old daily batch pipeline, old trending endpoints, and manual daily seed flow are no longer part of the active product path.

![Demo](demo.gif)
