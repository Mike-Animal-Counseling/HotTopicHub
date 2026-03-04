# AI Builder Daily Hub

A full-stack daily topic aggregation platform. Automatically fetches, deduplicates, clusters, and ranks the top 10 AI and builder-focused topics each day from multiple sources. Users can browse topics, leave comments, and like content. Admins can moderate comments through a dedicated dashboard.

## Tech Stack

**Backend**

- FastAPI
- SQLAlchemy
- SQLite

**Frontend**

- React (Vite)
- React Router

---

## Features

**Topics**

- Aggregates daily topics from HackerNews, GitHub Trending, Product Hunt, TechCrunch, and HuggingFace
- Deduplication, title clustering, and AI keyword filtering pipeline
- Source-balanced top 10 selection per day
- Topic ranking by engagement score (likes + comments)
- AI-generated summaries: key insights, why it matters, technical summary
- Topic history archive by date

**Comments**

- Submit comments on any topic
- Auto-moderation on submission (profanity, spam, rate limiting)
- Like comments
- Report comments
- Ranked highlights (Top Insight, Top Resource, Top Technical Comment)

**Admin**

- Token-protected moderation dashboard
- Pending review queue for flagged comments
- Approve, reject, hide, restore actions
- Processed list with reopen-for-review capability
- Reports and activity log tables

---

## Data Seeding

- Comment seed file: `backend/data/comments.json`
- The database auto-seeds on backend startup only if the comments table is empty.
- Topics are generated automatically on startup via the pipeline (no manual seed needed).

---

## API Endpoints

**Topics**

- `GET /api/topics` — list topics for a date
- `GET /api/topics/trending` — top 10 topics for a date
- `GET /api/topics/history` — list all daily batches
- `GET /api/topics/{id}` — get a single topic
- `POST /api/topics/seed-daily` — trigger pipeline manually
- `POST /api/topics/{id}/like` — like a topic
- `DELETE /api/topics/{id}/like` — unlike a topic

**Comments**

- `GET /api/topics/{id}/comments` — list all comments for a topic
- `GET /api/topics/{id}/comments/highlights` — ranked top comments
- `POST /api/topics/{id}/comments` — submit a comment
- `PATCH /api/comments/{id}` — edit a comment
- `DELETE /api/comments/{id}` — delete a comment
- `POST /api/comments/{id}/like` — like a comment
- `DELETE /api/comments/{id}/like` — unlike a comment
- `POST /api/comments/{id}/report` — report a comment

**Admin** (requires `X-Admin-Token` header)

- `GET /api/admin/moderation/queue` — pending review comments
- `GET /api/admin/moderation/processed` — recently approved/rejected comments
- `GET /api/admin/moderation/logs` — activity logs
- `GET /api/admin/reports` — open reports
- `PATCH /api/admin/comments/{id}` — approve, reject, hide, or restore
- `POST /api/admin/comments/{id}/reopen` — reopen for re-review

---

## Backend Setup

1. Navigate to the backend directory
   ```
   cd .\Bobyard-Comment\backend\
   ```
2. Create and activate a virtual environment
   ```
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
3. Install dependencies
   ```
   pip install -r requirements.txt
   ```
4. Start the backend server
   ```
   python -m uvicorn app.main:app --reload
   ```

The topic pipeline runs automatically on startup. The default admin token is `dev-admin-token` (override with `ADMIN_TOKEN` environment variable).

---

## Frontend Setup

1. Navigate to the frontend directory
   ```
   cd .\Bobyard-Comment\frontend\
   ```
2. Install dependencies
   ```
   npm install
   ```
3. Start the development server
   ```
   npm run dev
   ```

---

## Demo

![Demo](demo.gif)
