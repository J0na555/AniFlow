# AniFlow

AniFlow is a **Django** backend for tracking anime, syncing lists from **AniList**, and routing watch/play links through pluggable **streaming source** adapters. It ships with **server-rendered pages** for the full UI and a **JSON API** under `/api/` for a separate SPA (session cookies + CORS).

## Features

- **AniList OAuth** — Sign in with AniList, store tokens on the user, and sync the remote list into local `Anime` / `UserAnime` rows.
- **Library & progress** — Watching / completed lists, episode progress, status updates, optional watching limits (user settings).
- **Streaming resolution** — Maps catalog titles to provider-specific IDs, builds episode URLs, and falls back to provider search when mapping is missing or needs confirmation.
- **Dashboard data via API** — Endpoints such as `/api/me/`, `/api/dashboard/`, search, watchlist, resume, recommendations, and seasonal release info for SPA consumers.
- **Production-ready static files** — WhiteNoise serves collected static assets; `gunicorn` is the expected WSGI server.

## Stack

| Component | Choice |
|-----------|--------|
| Runtime | Python 3.12+ (Render blueprint pins 3.12.3) |
| Framework | Django 5.2 |
| Database | PostgreSQL (`DATABASE_URL`) |
| HTTP client / OAuth helpers | `httpx`, `requests-oauthlib` |
| Fuzzy matching | `rapidfuzz` (streaming title matching) |
| Server | `gunicorn` + WhiteNoise |

## Repository layout

- `config/` — Django project (`settings`, `urls`, WSGI/ASGI, CORS middleware).
- `apps/anime/` — Core models, web views, templates, and `/api/*` JSON handlers.
- `apps/users/` — Custom user model, AniList OAuth views (`/auth/...`), settings forms.
- `apps/tracker/` — Tracker abstraction; **AniList** adapter and list sync.
- `apps/streaming/` — `StreamingSource` models, matchers, router, and per-site adapters in `apps/streaming/sources/`.
- `apps/recommendations/`, `apps/releases/`, `apps/productivity/` — Supporting services used by the dashboard and API.

## Local development

### Prerequisites

- Python 3.12+
- A running **PostgreSQL** instance and a connection URL

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env
# Edit .env: set DATABASE_URL, SECRET_KEY, and AniList OAuth variables (see below).
python manage.py migrate
python manage.py runserver
```

Open `http://127.0.0.1:8000/` for the server-rendered app. Django admin is at `/admin/`.

### AniList OAuth

1. Create an API client at [AniList API settings](https://anilist.co/settings/developer).
2. Set **redirect URI** in AniList to exactly the value of `ANILIST_REDIRECT_URI` in your environment. For local Django that is typically:

   `http://127.0.0.1:8000/auth/anilist/callback/`

   (must match scheme, host, port, and path).

3. Set `ANILIST_CLIENT_ID`, `ANILIST_CLIENT_SECRET`, and `ANILIST_REDIRECT_URI` in `.env`.

Session and CSRF cookies can be tuned with `COOKIE_SECURE` and `COOKIE_SAMESITE` when the API and SPA run on different origins; see comments in `.env.example`.

### Tests

```bash
python manage.py test
```

## Environment variables

Copy `.env.example` and adjust. Commonly required:

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL URL (`postgresql://...`) |
| `SECRET_KEY` | Django secret |
| `DEBUG` | `1` for local dev, `0` in production |
| `ALLOWED_HOSTS` | Comma-separated hostnames |
| `CORS_ALLOWED_ORIGINS` | Origins allowed for `/api/` (e.g. `http://localhost:3000`) |
| `CSRF_TRUSTED_ORIGINS` | Often needed for cross-site POSTs in production |
| `ANILIST_CLIENT_ID` / `ANILIST_CLIENT_SECRET` / `ANILIST_REDIRECT_URI` | OAuth |
| `FRONTEND_URL` | Default post-login redirect when no `?next=` is provided |
| `COOKIE_SECURE` / `COOKIE_SAMESITE` | Cookie and cross-site session behavior |

Optional: `CORS_ALLOWED_ORIGIN_REGEXES`, `FRONTEND_ALLOWED_REDIRECT_ORIGINS` for preview deployments and safe redirects after login.

## HTTP surface

### Web UI (session auth)

Mounted at the site root in `config/urls.py` — dashboard, search, lists, play/resume redirects, settings-related flows, etc.

### Authentication

- `GET /auth/anilist/login/` — Start OAuth (supports vetted `?next=` redirect targets).
- `GET /auth/anilist/callback/` — OAuth callback (code exchange, session creation).
- Other routes under `/auth/` for completion, logout, and user settings.

### JSON API (for SPA)

All under `/api/` (see `apps/anime/api_urls.py`):

- `GET /api/me/` — Auth probe (always 200; `authenticated` flag).
- `GET /api/dashboard/` — Dashboard payload.
- `GET /api/anime/search/` — Search.
- `POST /api/sync/anilist/` — Trigger AniList sync.
- Watchlist, resume, progress, library add/status, recommendations, releases — see `api_urls.py` for paths and methods.

Unauthenticated API calls that require a user return **401 JSON** (`detail`, `code`) instead of an HTML redirect.

### Health

- `GET /health/` — Health check (anime app).

## Deployment (Render)

The repo includes `render.yaml` and step-by-step notes in [DEPLOY_RENDER.md](DEPLOY_RENDER.md): build (`pip`, `collectstatic`, `migrate`), start (`gunicorn config.wsgi:application`), and required production env vars (including `CSRF_TRUSTED_ORIGINS` and AniList callback URL on the backend host).

## Extending streaming providers

See [apps/streaming/sources/README.md](apps/streaming/sources/README.md) for adding an adapter, seeding `StreamingSource`, and how `resolve_streaming_route()` picks URLs.
