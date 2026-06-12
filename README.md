# Kafi Commodities — Social Media & Branding AI Agent

An end-to-end AI platform for **Kafi Commodities (Pvt) Ltd** to plan, create, approve, schedule, publish, and analyze social media content across LinkedIn, Facebook, Instagram, and YouTube — with competitor intelligence built in.

**Repository:** [github.com/izoo2003/Social-Media-Agent-With-Engagement-Rival-Analysis-](https://github.com/izoo2003/Social-Media-Agent-With-Engagement-Rival-Analysis-)

| Service | URL (local dev) |
|---------|-----------------|
| Dashboard | http://localhost:3000 |
| API | http://localhost:8000/api/v1 |
| API docs (dev only) | http://localhost:8000/docs |
| Uploaded media | http://localhost:8000/uploads |

---

## Table of Contents

- [What This Project Does](#what-this-project-does)
- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Dashboard Guide](#dashboard-guide)
- [Designer Approval Workflow](#designer-approval-workflow)
- [Security](#security)
- [API Overview](#api-overview)
- [Database & Migrations](#database--migrations)
- [Docker](#docker)
- [OAuth Setup](#oauth-setup)
- [Project Structure](#project-structure)
- [Roadmap & Known Gaps](#roadmap--known-gaps)
- [Documentation](#documentation)
- [License](#license)

---

## What This Project Does

Kafi Commodities exports spices, rice, and related agro-commodities globally. This system acts as an in-house **social media operations agent**:

1. **Generate** platform-specific captions with Google Gemini
2. **Attach** designer media (images/videos) via Supabase or local storage
3. **Review** posts through a designer PIN gate or email approval workflow
4. **Publish** live to LinkedIn (multi-account), Facebook, Instagram, and YouTube — or simulate in draft mode
5. **Schedule** posts on a calendar with a background auto-publisher
6. **Measure** engagement via live analytics from each platform API
7. **Benchmark** against competitors (Shan Foods, National Foods, etc.) with AI-generated insights

---

## Features

### Content Generation & Posting
- AI caption generation for LinkedIn, Facebook, Instagram, Twitter/X, TikTok, and YouTube
- Topic, tone, audience, CTA, and brand-context inputs
- Regenerate captions with user feedback
- Media upload (image, video, PDF) with magic-byte validation and SVG blocked (XSS prevention)
- Storage: **Supabase Storage** (production) or **local disk** (`backend/uploads/`)
- Live posting to LinkedIn (up to 3 accounts), Facebook Page, Instagram Business, YouTube
- `DRAFT_MODE` simulates posts without hitting APIs (safe for testing)
- Per-platform post status and post IDs tracked on every content record

### Content Calendar & Scheduler
- Visual month-grid calendar with upcoming-events sidebar
- Schedule posts with platform selection, caption overrides, and LinkedIn account subset
- Background worker (APScheduler) auto-publishes due events every 30 seconds
- Event lifecycle: `pending` → `publishing` → `published` | `partial` | `failed` | `cancelled`
- Publish-now, edit, reschedule, and cancel from the UI
- Stuck `publishing` events auto-reclaimed after server restarts

### Analytics Dashboard
- Live metrics from LinkedIn, Facebook, Instagram, and YouTube APIs
- Views/reach, engagements, followers, likes, comments, shares, watch time (YouTube)
- Date ranges: 7, 30, and 90 days
- Per-platform status: connected, not configured, permission error, API error
- Trend charts powered by Recharts

### Designer Approval Workflow (QA Checker)
- When `APPROVAL_REQUIRED=true`, non-designers cannot post directly
- **Designer path:** enter PIN → verify → post immediately
- **Team path:** submit for approval → SMTP email to designer with one-click approve/reject links
- QA Checker page: pending queue, approve & publish, reject with note
- Dashboard QA Pass Rate stat (`approved / (approved + rejected)`)
- Email magic links expire after 48 hours (configurable)
- PIN brute-force protection: 5 failed attempts → 15-minute IP lockout

### Content Creation Chatbot
- Separate Gemini-powered brainstorming assistant (`CREATION_GEMINI_API_KEY`)
- Multi-turn chat for campaign ideas, hooks, and caption drafts
- Deep link to Google Gemini web app for image/video creation
- Independent from the posting LLM key

### Rival Review (Competitor Intelligence)
- Track competitors with website, YouTube channel, Instagram, and RSS feeds
- Auto-seeds industry rivals (Shan Foods, National Foods, Mehran Foods, etc.)
- Collects public metrics via YouTube Data API, Meta Graph API, and web scraping
- Historical snapshots for trend charts
- AI insights (Gemini) comparing rival performance vs your own analytics
- Optional background auto-refresh

### Platform Settings
- Read-only view of which social platforms are configured
- LinkedIn multi-account labels and connection status
- OAuth helper routes for Meta and YouTube token renewal

### Security Hardening
- Per-IP rate limiting on LLM, upload, PIN, approval, and calendar endpoints
- Strict CORS from environment configuration
- Security headers (X-Frame-Options, nosniff, HSTS in production, etc.)
- Request body size limits (20 MB default)
- Sanitized error responses in production; `/docs` disabled in production
- Internal API key for destructive admin endpoints (`DELETE /content/clear-all`)
- Auto-generated dev API key saved to `backend/.internal_api_key`
- HTML escaping in approval emails; path traversal protection on media paths

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Next.js Dashboard (localhost:3000)                             │
│  Dashboard · Generator · Calendar · Analytics · QA · Rivals     │
└────────────────────────────┬────────────────────────────────────┘
                             │ REST /api/v1
┌────────────────────────────▼────────────────────────────────────┐
│  FastAPI Backend (localhost:8000)                               │
│  Routes → Services → LLM / Social APIs / Email / Scheduler      │
└──────┬──────────────┬──────────────┬──────────────┬──────────────┘
       │              │              │              │
  PostgreSQL    Google Gemini    Meta/LinkedIn/    Supabase
  (or Supabase)   (content +      YouTube APIs     Storage
                   creation)                      (or local disk)
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full system design.

---

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Frontend** | Next.js 14, React 18, TypeScript, Tailwind CSS, Recharts, date-fns, react-hot-toast |
| **Backend** | FastAPI, Uvicorn, Python 3.10+, Pydantic v2, SQLAlchemy 2 |
| **Database** | PostgreSQL 14+ or Supabase |
| **LLM** | Google Gemini API (primary); Ollama optional (`LLM_PROVIDER=ollama`) |
| **Storage** | Supabase Storage or local filesystem |
| **Scheduling** | APScheduler (background post worker) |
| **Rate limiting** | slowapi |
| **Email** | SMTP (Gmail App Password) for approval notifications |
| **Scraping** | BeautifulSoup, feedparser (rival collectors) |

---

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- PostgreSQL or Supabase database
- [Google Gemini API key](https://aistudio.google.com/apikey) (free tier)

### 1. Backend

```bash
cd backend
cp .env.example .env
# Edit .env: set DATABASE_URL, GEMINI_API_KEY, and social credentials

python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
python scripts/setup_db.py
python main.py
```

API runs at **http://localhost:8000**. Interactive docs at **http://localhost:8000/docs** (development only).

> In development, if `INTERNAL_API_KEY` is left blank, a key is auto-generated on first run and saved to `backend/.internal_api_key`.

### 2. Frontend

```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

Dashboard runs at **http://localhost:3000**.

### 3. Run migrations (if upgrading from an older version)

```bash
cd backend
python scripts/migrate_add_approvals.py
python scripts/migrate_add_token_expiry.py
```

---

## Configuration

### Essential backend variables (`backend/.env`)

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string |
| `GEMINI_API_KEY` | Content generation LLM |
| `CREATION_GEMINI_API_KEY` | Content Creation chatbot (separate key recommended) |
| `ENVIRONMENT` | `development` \| `staging` \| `production` |
| `CORS_ORIGINS` | Comma-separated frontend origins (e.g. `http://localhost:3000`) |
| `DRAFT_MODE` | `True` = simulate posts; `False` = live posting |
| `APPROVAL_REQUIRED` | `True` = designer gate on posting |
| `DESIGNER_PIN` | Shared PIN for designer actions |
| `DESIGNER_EMAIL` | Recipient for approval-request emails |
| `SMTP_*` | Gmail SMTP credentials for approval emails |
| `SUPABASE_URL` + `SUPABASE_SECRET_KEY` | Media storage (optional) |
| `INTERNAL_API_KEY` | Protects `DELETE /content/clear-all` (auto-set in dev) |

### Social platform credentials

| Platform | Key variables |
|----------|--------------|
| LinkedIn | `LINKEDIN_ACCESS_TOKEN`, `LINKEDIN_PERSON_ID`, `LINKEDIN_ORGANIZATION_ID`, multi-account `LINKEDIN_ACCOUNT_*` |
| Facebook / Instagram | `FACEBOOK_PAGE_ACCESS_TOKEN`, `FACEBOOK_PAGE_ID`, `INSTAGRAM_ACCOUNT_ID` |
| YouTube | `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`, `YOUTUBE_CHANNEL_ID` |
| Rival YouTube stats | `YOUTUBE_DATA_API_KEY` (public Data API, separate from upload OAuth) |

### Frontend variables (`frontend/.env.local`)

| Variable | Default |
|----------|---------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` |
| `NEXT_PUBLIC_APP_NAME` | `Kafi Social Agent` |

Copy the full list from `backend/.env.example` and `frontend/.env.local.example`.

---

## Dashboard Guide

| Page | Route | What it does |
|------|-------|--------------|
| **Dashboard** | `/dashboard` | Overview stats, recent drafts, QA pass rate, refresh |
| **Content Creation** | `/dashboard/creation` | AI chatbot for brainstorming and prompt crafting |
| **Content Posting** | `/dashboard/generator` | Upload media → generate captions → post or schedule |
| **Calendar** | `/dashboard/calendar` | Month view, schedule/edit/delete events, publish now |
| **Analytics** | `/dashboard/analytics` | Platform metrics and trend charts (7d/30d/90d) |
| **QA Checker** | `/dashboard/qa` | Designer approval queue — approve, reject, or publish |
| **Rival Review** | `/dashboard/rivals` | Competitor tracking, refresh, AI insights |
| **Settings** | `/dashboard/settings` | Platform configuration status |

---

## Designer Approval Workflow

```
Non-designer clicks "Post"
        │
        ▼
  APPROVAL_REQUIRED?
    │           │
   No          Yes
    │           │
    ▼           ▼
 Post now   Has designer PIN?
              │           │
             Yes          No
              │           │
              ▼           ▼
           Post now   Submit approval
                          │
                          ▼
                    Email to designer
                    (approve / reject links)
                          │
                          ▼
                    QA Checker page
                    or email one-click
                          │
                          ▼
                    Approve → publish
                    Reject  → note saved
```

Configure in `.env`:

```env
APPROVAL_REQUIRED=True
DESIGNER_PIN=your-pin
DESIGNER_EMAIL=designer@company.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your@gmail.com
SMTP_PASSWORD=your-gmail-app-password
```

---

## Security

| Control | Details |
|---------|---------|
| Rate limiting | LLM: 10/min, uploads: 20/min, PIN: 5/min, calendar: 30/min |
| CORS | Explicit origins from `CORS_ORIGINS`; no wildcards |
| Security headers | nosniff, DENY framing, HSTS (production), no-store cache |
| Body size limit | 20 MB default (`MAX_REQUEST_BODY_MB`) |
| File uploads | Extension whitelist, magic-byte checks, no SVG |
| PIN lockout | 5 failures → 15-minute IP ban |
| Approval tokens | 48-hour expiry on email magic links |
| Internal API key | Required header `X-Internal-API-Key` for `DELETE /content/clear-all` |
| Error sanitization | Production returns generic messages; details logged server-side |
| API docs | Disabled when `ENVIRONMENT=production` |

---

## API Overview

Base path: `/api/v1`

| Module | Key endpoints |
|--------|--------------|
| **Health** | `GET /health`, `GET /health/detailed` |
| **Content** | `POST /content/generate`, `POST /content/generate-with-media`, `GET /content/history`, `POST /content/{id}/post` |
| **Calendar** | `GET /calendar/events`, `POST /calendar/events`, `POST /calendar/events/{id}/publish-now` |
| **Analytics** | `GET /analytics/summary`, `GET /analytics/{platform}` |
| **Approvals** | `GET /approvals`, `POST /approvals`, `POST /designer/verify-pin`, `GET /approvals/review/{token}` |
| **Creation** | `GET /creation/models`, `POST /creation/chat` |
| **Rivals** | `GET /rivals`, `POST /rivals/{id}/refresh`, `GET /rivals/insights` |
| **Social** | `GET /social/platforms/config`, `GET /social/linkedin/accounts` |
| **OAuth** | `GET /auth/meta`, `GET /auth/youtube` (+ callbacks) |

Full reference: [docs/API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md) and `/docs` in development.

---

## Database & Migrations

### Core tables

| Table | Purpose |
|-------|---------|
| `content` | Generated posts, media paths, per-platform publish status |
| `calendar_event` | Scheduled posts and execution results |
| `approval_request` | Designer approval queue with magic-link tokens |
| `rival` / `rival_snapshot` | Competitor tracking and historical metrics |
| `qa_report` | QA compliance results (schema ready) |
| `analytics_metric` | Metrics cache (schema ready) |

### Scripts

| Script | When to run |
|--------|-------------|
| `scripts/setup_db.py` | First-time setup — creates all tables |
| `scripts/migrate_add_approvals.py` | Adds approval workflow table |
| `scripts/migrate_add_token_expiry.py` | Adds token expiry column to approvals |
| `scripts/migrate_calendar.py` | Calendar scheduling columns |
| `scripts/migrate_add_youtube_columns.py` | YouTube post tracking on content |
| `scripts/migrate_linkedin_multi_account.py` | Multi-account LinkedIn results |
| `scripts/reset_db.py` | **Destructive** — drops and recreates all tables |

---

## Docker

```bash
docker-compose up -d
```

| Service | Port | Notes |
|---------|------|-------|
| `postgres` | 5432 | Database (`kafi_social_agent`) |
| `backend` | 8000 | FastAPI with hot reload |
| `frontend` | 3000 | Next.js dev server |

Docker provides the infrastructure; you still need a populated `backend/.env` for Gemini, social APIs, and SMTP.

---

## OAuth Setup

When Meta or YouTube tokens expire, use the built-in OAuth helpers:

| Platform | Start URL |
|----------|-----------|
| Meta (Facebook + Instagram) | http://localhost:8000/api/v1/auth/meta |
| YouTube | http://localhost:8000/api/v1/auth/youtube |

Callbacks display tokens to paste into `backend/.env`.

---

## Project Structure

```
Social-Media-Agent-With-Engagement-Rival-Analysis-/
├── frontend/
│   └── src/
│       ├── app/dashboard/       # All dashboard pages
│       ├── components/          # Generator, calendar, creation, approval UI
│       └── lib/                 # API client, TypeScript types
├── backend/
│   ├── main.py                  # FastAPI entry + middleware stack
│   ├── app/
│   │   ├── routes/              # API endpoints
│   │   ├── services/            # Business logic, scheduler, email
│   │   ├── middleware/          # CORS, rate limit, security, errors
│   │   ├── database/            # SQLAlchemy models
│   │   ├── llm/                 # Gemini / Ollama client
│   │   └── agents/              # Multi-agent stubs (future)
│   ├── scripts/                 # Setup, migrations, diagnostics
│   └── uploads/                 # Local media fallback
├── docs/                        # Architecture, API, setup guides
├── docker-compose.yml
├── Dockerfile.backend
├── Dockerfile.frontend
└── README.md
```

---

## Roadmap & Known Gaps

| Area | Status |
|------|--------|
| Content generation, posting, calendar, analytics, rivals | **Implemented** |
| Designer approval + email magic links | **Implemented** |
| Security hardening (rate limits, CORS, headers, sanitization) | **Implemented** |
| Multi-agent QA compliance (`POST /qa/check`) | Stub — not wired to UI |
| Scraper management (`/scraper/*`) | Stub |
| Analytics trends endpoint | Returns empty data |
| User authentication (JWT / `User` model) | Placeholder |
| Dashboard "Clear All" button | Requires `X-Internal-API-Key` header (not yet sent from UI) |

---

## Documentation

- [Architecture Guide](docs/ARCHITECTURE.md)
- [API Documentation](docs/API_DOCUMENTATION.md)
- [Setup Guide](docs/SETUP_GUIDE.md)
- [Project Status](docs/PROJECT_STATUS.md)

---

## License

MIT License

---

## Author

Built for **Kafi Commodities (Pvt) Ltd** — Global Agro-Commodity Exporter
