# Deploy AniFlow backend on Render

## 1) Create the web service
- Connect this repo in Render.
- Render should detect `render.yaml` automatically; if not, create a Python Web Service manually.
- Build command:
  - `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate`
- Start command:
  - `gunicorn config.wsgi:application`

## 2) Set required environment variables
- `DATABASE_URL` (from Render Postgres)
- `SECRET_KEY` (Render can generate)
- `DEBUG=0`
- `ALLOWED_HOSTS=.onrender.com`
- `COOKIE_SECURE=1`
- `CORS_ALLOWED_ORIGINS=https://YOUR_FRONTEND_DOMAIN`
- `CSRF_TRUSTED_ORIGINS=https://YOUR_FRONTEND_DOMAIN,https://YOUR_BACKEND.onrender.com`
- `ANILIST_REDIRECT_URI=https://YOUR_BACKEND.onrender.com/auth/anilist/callback/`
- `ANILIST_CLIENT_ID` and `ANILIST_CLIENT_SECRET`

## 3) Most common failure causes
- Missing `DATABASE_URL` -> app crashes at boot.
- Missing `SECRET_KEY` -> app crashes at boot.
- Not setting `CSRF_TRUSTED_ORIGINS` -> 403 on POST requests.
- Wrong `ANILIST_REDIRECT_URI` -> OAuth callback/token errors.
- Frontend domain not in `CORS_ALLOWED_ORIGINS` -> browser CORS failures.

## 4) Verify after deploy
- Open `https://YOUR_BACKEND.onrender.com/`
- Check `https://YOUR_BACKEND.onrender.com/api/dashboard/` after login.
- Run AniList login end-to-end using the Render callback URL.
