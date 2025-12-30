# Railway Deployment Guide

## Prerequisites

Your app is ready for Railway deployment! Here's what you need:

1. Railway account (https://railway.app)
2. GitHub repository (push your code)
3. PostgreSQL database (Railway provides this)
4. Redis instance (Railway provides this)

## Architecture on Railway

Railway will run 3 separate services:
1. **Web** (Django + Gunicorn) - Main app
2. **Worker** (Celery) - Background tasks for LLM enrichment
3. **Redis** - Message broker for Celery

## Step-by-Step Deployment

### 1. Create New Project on Railway

1. Go to https://railway.app
2. Click "New Project"
3. Choose "Deploy from GitHub repo"
4. Select your `memoria.uy` repository

### 2. Add PostgreSQL Database

1. In your Railway project, click "+ New"
2. Select "Database" → "PostgreSQL"
3. Railway will automatically create `DATABASE_URL` environment variable

### 3. Add Redis

1. Click "+ New" again
2. Select "Database" → "Redis"
3. Railway will create `REDIS_URL` environment variable

### 4. Configure Web Service

This is your main Django app.

**Environment Variables to set:**

```
DEBUG=False
SECRET_KEY=<generate-a-strong-secret-key>
ALLOWED_HOSTS=memoria.uy,www.memoria.uy
CSRF_TRUSTED_ORIGINS=https://memoria.uy,https://www.memoria.uy
CORS_ALLOWED_ORIGINS=https://memoria.uy,https://www.memoria.uy
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
GOOGLE_API_KEY=<your-gemini-api-key>
OPENROUTER_API_KEY=<your-openrouter-key>
```

**Note:**
- Railway automatically provides `RAILWAY_PUBLIC_DOMAIN` which is auto-added to `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, and `CORS_ALLOWED_ORIGINS`
- Service references like `${{Postgres.DATABASE_URL}}` are automatically replaced by Railway
- You only need to add your custom domains (like memoria.uy) to the variables above

**Build & Deploy Settings:**
- Builder: Dockerfile
- Start Command: `gunicorn memoria.wsgi:application --bind 0.0.0.0:$PORT`

### 5. Add Celery Worker Service

Create a **second service** from the same repository.

**Environment Variables:**
Same as web service (Railway can copy them)

**Build & Deploy Settings:**
- Builder: Dockerfile
- Start Command: `celery -A memoria worker --loglevel=info`

### 6. Run Database Migrations

After first deployment, run migrations:

1. Go to Web service
2. Click "Settings" → "Deploy"
3. Click "Run Command"
4. Run: `python manage.py migrate`

Or use Railway CLI:
```bash
railway run python manage.py migrate
```

### 7. Create Superuser

```bash
railway run python manage.py createsuperuser
```

### 8. Collect Static Files

Railway doesn't have persistent storage, so you need to use a CDN or whitenoise.

**Option 1: Use WhiteNoise (Recommended)**

Already configured in your settings! Just make sure static files are collected:

```bash
railway run python manage.py collectstatic --noinput
```

**Option 2: Use S3/Cloudflare R2**

Add django-storages and configure in settings.py.

## Environment Variables Reference

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `DATABASE_URL` | Yes | PostgreSQL connection (auto-set) | `postgresql://...` |
| `REDIS_URL` | Yes | Redis connection (auto-set) | `redis://...` |
| `SECRET_KEY` | Yes | Django secret key | Generate with `python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'` |
| `DEBUG` | Yes | Should be False in production | `False` |
| `ALLOWED_HOSTS` | Yes | Domains allowed to serve | `*.railway.app,memoria.uy` |
| `CSRF_TRUSTED_ORIGINS` | Yes | CSRF allowed origins | `https://*.railway.app` |
| `GOOGLE_API_KEY` | Yes | For Gemini LLM | Your API key |
| `OPENROUTER_API_KEY` | Optional | Fallback LLM | Your API key |

## Health Checks

Railway will check `/health/` endpoint to ensure app is running.

Already configured in [core/views.py](core/views.py).

## Troubleshooting

### Static files not loading
- Run `python manage.py collectstatic`
- Check STATIC_ROOT and STATIC_URL in settings
- Consider using WhiteNoise (already configured)

### Celery worker not processing tasks
- Check worker service logs
- Verify REDIS_URL is same across web and worker
- Check Celery logs: `railway logs --service worker`

### Database migrations failed
- Run manually: `railway run python manage.py migrate`
- Check DATABASE_URL is set correctly

### Extension can't connect to API
- Update extension's API URL to your Railway URL
- Add Railway URL to CORS_ALLOWED_ORIGINS
- Update CSRF_TRUSTED_ORIGINS

## Scaling

Railway allows horizontal scaling:
- **Web**: Can run multiple instances (load balanced)
- **Worker**: Can run multiple instances (tasks distributed)
- **Redis**: Single instance (managed by Railway)
- **PostgreSQL**: Managed by Railway with auto-backups

## Cost Estimate

Railway pricing (as of 2024):
- **Hobby Plan**: $5/month
  - 500 hours execution time
  - Enough for small-medium traffic
- **Add-ons**:
  - PostgreSQL: Included
  - Redis: Included
  - Custom domain: Free

**Total estimated cost**: ~$5-10/month for MVP

## Custom Domain

1. Go to your web service
2. Click "Settings" → "Domains"
3. Add your custom domain (e.g., memoria.uy)
4. Add CNAME record in your DNS:
   - Name: `@` or `www`
   - Value: `<your-railway-domain>.railway.app`

## Monitoring

Railway provides:
- **Logs**: Real-time logs for each service
- **Metrics**: CPU, Memory, Network usage
- **Deployments**: History of all deployments

## Deployment Workflow

Every push to main branch will trigger automatic deployment:

1. Push to GitHub
2. Railway detects changes
3. Builds Docker image
4. Runs new containers
5. Zero-downtime deployment

## Next Steps

After deploying:

1. ✅ Test extension connection to production API
2. ✅ Submit test article and check Celery logs
3. ✅ Verify LLM enrichment works
4. ✅ Check entity extraction
5. ✅ Monitor costs and usage

## Support

- Railway Docs: https://docs.railway.app
- Railway Discord: https://discord.gg/railway
- Check logs: `railway logs`

---

**Your app is Railway-ready!** 🚀

Main differences from local:
- Uses managed PostgreSQL instead of SQLite
- Uses managed Redis for Celery
- Static files served via WhiteNoise
- Auto-deployments from GitHub
