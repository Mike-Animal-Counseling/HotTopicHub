# HotTopicHub

**AI Builder Daily Hub — discover what's new in AI, discuss what matters.**

A full-stack hub that brings AI-builder news from multiple sources into one live feed, then turns community engagement into a daily Top 10.

[Demo](#demo) · [Features](#features) · [Quick start](#quick-start) · [Configuration](#configuration) · [Developer guide](docs/development.md) · [Security](SECURITY.md)

## Demo

<p align="center">
  <img src="demo-release0.gif" alt="HotTopicHub product demo" width="880" />
</p>

<p align="center"><em>Live discovery, daily community signals, and topic discussions in one place.</em></p>

## Features

| Surface | What you can do |
| --- | --- |
| **Live Feed** | Browse a continuous stream from Hacker News, GitHub Trending, Product Hunt, Reddit, and RSS feeds. Refresh for new topics or load more as you read. |
| **Daily Top 10** | Find the strongest signals from the last 24 hours, ranked by likes, comments, source clicks, and recency, with a cap per source. |
| **Daily History** | Revisit previous daily signal sets by date. |
| **Topic discussions** | Read summaries, key insights, why a topic matters, and technical context. Join the discussion, like comments, or follow the original source. |

**AI enrichment** adds editorial context through OpenRouter, with template-based fallback when AI is unavailable. **Moderation tools** support automatic comment review, reports, and an admin review queue.

## Quick start

Built with **React + Vite + React Router** on the frontend and **FastAPI + SQLAlchemy + SQLite** on the backend.

You'll need Python 3.12+ and Node.js 20.19+ (20.x) or 22.12+. Run the backend and frontend in separate terminals.

```bash
git clone https://github.com/Mike-Animal-Counseling/HotTopicHub.git
cd HotTopicHub
```

### 1. Start the backend

From the repository root, in PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

<details>
<summary>macOS / Linux commands</summary>

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

</details>

The backend creates its SQLite database, refreshes the feed, and syncs recent items into topics on startup. Model downloads are optional and disabled by default.

### 2. Start the frontend

In a second terminal, from the repository root:

```bash
cd frontend
npm ci
npm run dev
```

Open the app at **[localhost:5173](http://localhost:5173)**. The backend runs at [127.0.0.1:8000](http://127.0.0.1:8000), with interactive API documentation at [/docs](http://127.0.0.1:8000/docs).

## Configuration

The default is a read-only demo with admin access disabled. Copy [`backend/.env.example`](backend/.env.example) to `backend/.env` to configure optional features, then restart the backend.

To try anonymous comments, likes, and reports locally, set `ALLOW_ANONYMOUS_INTERACTIONS=true`. Without a working moderation model, comments wait for admin review. To enable automatic text moderation, install `backend/requirements-moderation.txt` in the backend virtual environment and set `MODERATION_MODEL_ENABLED=true`; the first enabled launch downloads model weights. Image attachments always need manual review.

The app uses template-based summaries without an OpenRouter key. For AI enrichment, set:

```dotenv
AI_ENRICHMENT_ENABLED=true
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_MODEL=deepseek/deepseek-chat
```

For moderation tools, generate a random `ADMIN_TOKEN` of at least 32 characters in `backend/.env`, then enter it on the app's **Admin** page. There is no default admin token. Admin credentials are stored only for the current browser tab. Visitors can reload the latest feed; only admins can force a fresh collection.

Before exposing an instance, follow the deployment requirements in [SECURITY.md](SECURITY.md). See [CONTRIBUTING.md](CONTRIBUTING.md) for checks and dependency updates.

See the [developer guide](docs/development.md) for the data flow, backend routes, and main source files.
