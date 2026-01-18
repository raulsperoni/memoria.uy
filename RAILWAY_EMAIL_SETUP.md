# Railway Email Reengagement Setup Checklist

## Required Environment Variables

Set these in your Railway project environment variables:

### 1. Enable Reengagement Emails (REQUIRED)
```
ENABLE_REENGAGEMENT_EMAILS=True
```
**This is the most critical one** - without this, the task won't be scheduled at all.

### 2. Email Configuration (REQUIRED)
```
EMAIL_HOST_PASSWORD=your_resend_api_key
EMAIL_HOST_USER=resend
EMAIL_HOST=smtp.resend.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=memoria.uy <noreply@memoria.uy>
```

### 3. Email Schedule (Optional - defaults shown)
```
REENGAGEMENT_EMAIL_HOUR=10        # Default: 10 (10:00 AM UTC)
REENGAGEMENT_EMAIL_MINUTE=0        # Default: 0
REENGAGEMENT_DAYS_INACTIVE=7       # Default: 7 days
REENGAGEMENT_MAX_EMAILS=500        # Default: 500 emails per run
```

### 4. Redis (REQUIRED for Celery)
```
REDIS_URL=your_redis_url
```

## Services Required

Make sure these services are running in Railway:

1. **Beat Service** (`railway.beat.toml`)
   - Runs Celery beat scheduler
   - Command: `/entrypoint.sh beat`
   - This schedules the tasks

2. **Worker Service** (`railway.worker.toml`)
   - Runs Celery worker
   - Command: `/entrypoint.sh worker`
   - This processes the tasks

3. **Web Service** (optional for emails, but needed for the app)
   - Command: `/entrypoint.sh web`

## Timezone Note

⚠️ **Important**: Railway runs in UTC timezone. 

- Default schedule is `hour=10, minute=0` = **10:00 AM UTC**
- If you want 10:00 AM in Uruguay (UTC-3), set `REENGAGEMENT_EMAIL_HOUR=13` (10 AM + 3 hours)

## Debugging Steps

1. **Check if beat service is running:**
   - Go to Railway dashboard → Beat service → Logs
   - Look for: "Starting Celery beat..."
   - Should see scheduled tasks listed

2. **Check if task is scheduled:**
   - In beat logs, you should see the schedule including `send-reengagement-emails`
   - If `ENABLE_REENGAGEMENT_EMAILS` is not set, this task won't appear

3. **Check worker logs:**
   - Go to Railway dashboard → Worker service → Logs
   - When the task runs, you'll see logs from `core.tasks.send_reengagement_emails`

4. **Check for errors:**
   - Look for "Failed to send reengagement email" errors
   - Check email configuration if emails fail

5. **Test manually:**
   - You can trigger the task manually via Django shell:
   ```python
   from core.tasks import send_reengagement_emails
   result = send_reengagement_emails()
   print(result)
   ```

## Common Issues

### Issue: Emails not being sent
- ✅ Check `ENABLE_REENGAGEMENT_EMAILS=True` is set
- ✅ Check beat service is running
- ✅ Check worker service is running
- ✅ Check email credentials are correct
- ✅ Check logs for errors

### Issue: Task scheduled but not running
- ✅ Check worker service is running
- ✅ Check Redis connection is working
- ✅ Check worker logs for errors

### Issue: Wrong time
- ✅ Remember Railway uses UTC
- ✅ Adjust `REENGAGEMENT_EMAIL_HOUR` accordingly
