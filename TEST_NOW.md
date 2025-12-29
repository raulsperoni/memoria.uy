# Test Your MVP Right Now (5 Minutes)

## Quick Start

```bash
# 1. Start the server
poetry run python manage.py runserver

# 2. Open browser
open http://localhost:8000

# 3. Try these:
```

---

## Test Checklist ✅

### Test 1: Anonymous Submission (No Login)
1. **Go to:** http://localhost:8000
2. **You should see:** Timeline of news (might be empty or have existing items)
3. **Submit a URL:** Try `https://www.bbc.com/news`
4. **Vote:** Click "😊 Buena" or "😞 Mala"
5. **Check:** Article appears instantly (< 1 second)

**✅ Pass if:** No login prompt, article shows up fast

### Test 2: Anonymous Voting Persists
1. **Vote on a few articles**
2. **Close browser completely**
3. **Reopen:** http://localhost:8000
4. **Click:** "Mis Votos" filter (if available)

**✅ Pass if:** Your votes are still there

### Test 3: Vote Counts Work
1. **Vote on an article:** 😊 Buena
2. **Check vote count:** Should show "😊 1" (or more if others voted)
3. **Change vote to:** 😞 Mala
4. **Check:** Count updates (😞 1, 😊 decreases)

**✅ Pass if:** Counts update in real-time

### Test 4: Filter by Opinion
1. **Vote "Buena" on article A**
2. **Vote "Mala" on article B**
3. **Click filter:** "Mis Votos Buenas" (or similar)
4. **Check:** Only article A shows

**✅ Pass if:** Filter works with anonymous votes

### Test 5: Multiple URLs
1. **Submit:** BBC article
2. **Submit:** CNN article
3. **Submit:** Guardian article
4. **Check:** All 3 appear in timeline

**✅ Pass if:** All URLs accepted, meta tags extracted

---

## Expected Behavior

### What Should Work ✅
- [x] Visit site without login
- [x] Submit URL instantly (< 1 second)
- [x] Vote without account
- [x] See vote counts
- [x] Filter "My Votes"
- [x] Refresh page - votes still there

### What Won't Work (Expected) ⚠️
- [ ] Archive links (removed)
- [ ] AI summaries (removed)
- [ ] Entity extraction (removed)
- [ ] "Refresh" button (admin only, might not work)

---

## If Something Breaks

### Error: "Login Required"
**Problem:** Old code still has `LoginRequiredMixin`
**Fix:** Check `core/views.py` - VoteView and NoticiaCreateView should NOT have LoginRequiredMixin

### Error: "Field does not exist"
**Problem:** Templates reference removed fields
**Fix:** Search templates for `archivo_url`, `.titulo`, `.resumen` and remove/update

### Error: "Slow submission (> 5 seconds)"
**Problem:** Still calling archive somewhere
**Fix:** Check `core/views.py` - NoticiaCreateView should NOT call `find_archived()`

### Error: "Session error"
**Problem:** Session middleware not enabled
**Fix:** Check `memoria/settings.py` - `SessionMiddleware` should be in MIDDLEWARE

---

## Debug Commands

```bash
# Check database
poetry run python manage.py shell -c "
from core.models import Noticia, Voto
print(f'Noticias: {Noticia.objects.count()}')
print(f'Votos: {Voto.objects.count()}')
print(f'Anonymous: {Voto.objects.filter(usuario__isnull=True).count()}')
"

# Check migrations applied
poetry run python manage.py showmigrations core

# Check for errors
poetry run python manage.py check
```

---

## Test URLs to Try

**News Sites (Good for Testing):**
- https://www.bbc.com/news
- https://www.cnn.com
- https://www.theguardian.com/us
- https://www.nytimes.com
- https://www.washingtonpost.com

**Why these:** Good meta tags (title, image), fast to load

**Local News (If you want Spanish):**
- https://www.elobservador.com.uy
- https://ladiaria.com.uy

---

## Performance Targets

| Action | Target | Red Flag |
|--------|--------|----------|
| Page load | < 1s | > 3s |
| Submit URL | < 1s | > 3s |
| Vote | < 200ms | > 1s |
| Filter | < 500ms | > 2s |

---

## Success Criteria

**MVP is successful if:**
1. ✅ You can vote without login
2. ✅ Page loads fast (< 1s)
3. ✅ No errors in browser console
4. ✅ Votes persist across sessions
5. ✅ You'd actually use this yourself

**If all 5 pass → SHIP IT** 🚀

---

## Next Steps After Testing

### If Tests Pass ✅
1. **Invite 5 friends** to test
2. **Deploy to free hosting** (Render/Railway)
3. **Gather feedback**
4. **Iterate**

### If Tests Fail ❌
1. **Note which test failed**
2. **Check error logs** (`poetry run python manage.py runserver` output)
3. **Read [MVP_COMPLETE.md](MVP_COMPLETE.md)** for troubleshooting
4. **Ask for help** (provide error message)

---

**Time to Test:** ~5 minutes
**Time to Fix Issues:** ~30 minutes if any

**GO TEST IT NOW!** 🚀
