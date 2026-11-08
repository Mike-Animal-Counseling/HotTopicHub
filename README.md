# HotTopicHub

**AI Builder Daily Hub — discover what's new in AI, discuss what matters.**

A full-stack hub that pulls AI-builder news from several sources into one live feed,
then turns community engagement into a daily Top 10.

[Quick start](#quick-start) · [Features](#features) · [Configuration](#configuration) · [Developer guide](docs/development.md) · [Security](SECURITY.md)

<p align="center">
  <img src="https://raw.githubusercontent.com/Mike-Animal-Counseling/hot-topic-hub/c3d02a53c043aecdf0f16bbbba4bc15efb26b155/demo-release0.gif" alt="HotTopicHub product demo" width="880" />
</p>

## Features

- **Live feed** — Hacker News, GitHub Trending, Product Hunt, Reddit, and RSS in one stream, with refresh and pagination.
- **Daily Top 10** — the strongest signals from the last 24 hours, ranked by likes, comments, source clicks, and recency, with a per-source cap.
- **Daily history** — revisit previous daily signal sets by date.
- **Topic discussions** — summaries, key insights, why a topic matters, comments, likes, and source links.

AI enrichment through OpenRouter adds editorial context, with template-based fallbacks
when no key is configured. Moderation tools cover comment review, reports, and an admin queue.

## Quick start

React + Vite + React Router on the frontend; FastAPI + SQLAlchemy + SQLite on the backend.
Requires Python 3.12+ and Node.js 20.19+ or 22.12+. Run the two services in separate terminals.

Backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

On macOS or Linux, activate with `source .venv/bin/activate` instead.

Frontend:

```bash
cd frontend
npm ci
npm run dev
```

Open **http://localhost:5173**. The API runs at `http://127.0.0.1:8000`, with
interactive documentation at `/docs`.

## Configuration

The default is a read-only demo with admin access disabled. Copy
[`backend/.env.example`](backend/.env.example) to `backend/.env`, then restart the backend.

| Setting | Effect |
| --- | --- |
| `ALLOW_ANONYMOUS_INTERACTIONS=true` | Allow anonymous comments, likes, and reports locally. Without a moderation model, comments wait for review. |
| `AI_ENRICHMENT_ENABLED=true` + `OPENROUTER_API_KEY` | Enable AI summaries. Template-based summaries are used otherwise. |
| `ADMIN_TOKEN` | A random token of at least 32 characters, entered on the Admin page. There is no default token. |

Image attachments always need manual review. Before exposing an instance, follow the
deployment requirements in [SECURITY.md](SECURITY.md); checks and dependency updates are
in [CONTRIBUTING.md](CONTRIBUTING.md). See the [developer guide](docs/development.md) for
data flow, backend routes, and main source files.
