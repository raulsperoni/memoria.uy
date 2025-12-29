# Authentication Strategy - Anonymous First

## Problem

**Current:** Login required to vote
- ❌ High friction (must create account first)
- ❌ Kills viral growth (people won't sign up to test)
- ❌ Doesn't work well with extension (needs OAuth flow)
- ❌ Privacy concern (forces identity disclosure upfront)

**Your insight:** Start anonymous, optionally claim later

---

## New Strategy: Progressive Authentication

### Phase 1: Anonymous Voting (Session-Based)

**How it works:**
1. User visits site → Django creates session cookie automatically
2. User votes → Vote tied to session ID (not user account)
3. User closes browser → Comes back, still has their votes (cookie persists)
4. User clears cookies → Loses vote history (acceptable for MVP)

**Benefits:**
- ✅ Zero friction (instant voting)
- ✅ Privacy-first (no PII collected)
- ✅ Works perfectly with extension (extension sends session cookie)
- ✅ Can still do clustering (session IDs are stable identifiers)

**Technical:**
```python
# models.py
class Voto(models.Model):
    # OLD: usuario = ForeignKey(User, on_delete=CASCADE) - REQUIRED
    # NEW: usuario optional, session_key as fallback
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    session_key = models.CharField(max_length=40, null=True, blank=True)  # Anonymous votes
    noticia = models.ForeignKey(Noticia, on_delete=models.CASCADE)
    opinion = models.CharField(max_length=10, choices=[...])
    fecha_voto = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Can't use unique_together anymore (usuario can be null)
        # Use unique constraint with condition
        constraints = [
            models.UniqueConstraint(
                fields=['usuario', 'noticia'],
                condition=models.Q(usuario__isnull=False),
                name='unique_user_vote'
            ),
            models.UniqueConstraint(
                fields=['session_key', 'noticia'],
                condition=models.Q(session_key__isnull=False),
                name='unique_session_vote'
            )
        ]
```

### Phase 2: Optional Account Creation

**User journey:**
1. User votes anonymously (5-10 times)
2. System shows: "🎯 Want to see your votes on other devices? Create free account"
3. User clicks → Simple signup (email + password OR social auth)
4. System **migrates** anonymous votes to account
5. User now logged in, votes persist across devices

**Benefits:**
- ✅ Only ask for account when user is invested
- ✅ Don't lose anonymous vote data
- ✅ Clear value prop: "sync across devices"

**Technical:**
```python
# views.py
def claim_anonymous_votes(request):
    """
    After user signs up, migrate their session votes to account.
    Called automatically after successful registration.
    """
    if request.user.is_authenticated and request.session.session_key:
        # Find all votes from this session
        anonymous_votes = Voto.objects.filter(
            session_key=request.session.session_key,
            usuario__isnull=True
        )

        # Migrate to user account
        for vote in anonymous_votes:
            # Check if user already has a vote on this noticia
            existing = Voto.objects.filter(
                usuario=request.user,
                noticia=vote.noticia
            ).first()

            if not existing:
                vote.usuario = request.user
                vote.session_key = None  # Clear session, now tied to user
                vote.save()
            else:
                # User already voted as logged-in user, delete anonymous vote
                vote.delete()

        messages.success(request, f"Claimed {anonymous_votes.count()} of your votes!")
```

### Phase 3: Social + Guest Accounts

**Later enhancements:**
- Social login (Google, GitHub) - Easy signup
- "Guest" accounts - Auto-created, user can claim later
- Device fingerprinting - Recognize returning users even without cookies (privacy-respecting)

---

## Implementation Plan

### Step 1: Update Models

**File:** `core/models.py`

```python
class Voto(models.Model):
    """
    User vote on a news article.
    Can be anonymous (session-based) or authenticated (user account).
    """
    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Authenticated user (optional)"
    )
    session_key = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        db_index=True,
        help_text="Session ID for anonymous votes"
    )
    noticia = models.ForeignKey(Noticia, on_delete=models.CASCADE, related_name="votos")
    opinion = models.CharField(
        max_length=10,
        choices=[
            ("buena", "Buena noticia"),
            ("mala", "Mala noticia"),
            ("neutral", "Neutral"),
        ],
    )
    fecha_voto = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # One vote per user per article (if logged in)
            models.UniqueConstraint(
                fields=['usuario', 'noticia'],
                condition=models.Q(usuario__isnull=False),
                name='unique_user_vote'
            ),
            # One vote per session per article (if anonymous)
            models.UniqueConstraint(
                fields=['session_key', 'noticia'],
                condition=models.Q(session_key__isnull=False),
                name='unique_session_vote'
            )
        ]

    def __str__(self):
        voter = self.usuario.username if self.usuario else f"Session {self.session_key[:8]}"
        return f"{voter} - {self.opinion} - {self.noticia.mostrar_titulo[:50]}"

    @property
    def is_anonymous(self):
        return self.usuario is None

    def clean(self):
        """Ensure either usuario or session_key is set, not both."""
        if not self.usuario and not self.session_key:
            raise ValidationError("Vote must have either usuario or session_key")
        if self.usuario and self.session_key:
            raise ValidationError("Vote cannot have both usuario and session_key")
```

**Migration:**
```bash
poetry run python manage.py makemigrations core
# Creates migration to:
# 1. Make usuario nullable
# 2. Add session_key field
# 3. Remove old unique_together constraint
# 4. Add new UniqueConstraint conditions
```

### Step 2: Update Views

**File:** `core/views.py`

```python
# Remove LoginRequiredMixin from views
class VoteView(View):  # NOT LoginRequiredMixin anymore
    def post(self, request, pk):
        noticia = get_object_or_404(Noticia, pk=pk)
        opinion = request.POST.get("opinion")

        if opinion not in ["buena", "mala", "neutral"]:
            return HttpResponseBadRequest("Invalid vote")

        # Get voter identifier (user or session)
        if request.user.is_authenticated:
            voter_kwargs = {'usuario': request.user}
            lookup_kwargs = {'usuario': request.user, 'noticia': noticia}
        else:
            # Anonymous vote - use session
            if not request.session.session_key:
                request.session.create()  # Force session creation
            voter_kwargs = {'session_key': request.session.session_key}
            lookup_kwargs = {'session_key': request.session.session_key, 'noticia': noticia}

        # Update or create vote
        Voto.objects.update_or_create(
            **lookup_kwargs,
            defaults={**voter_kwargs, 'opinion': opinion}
        )

        # Render updated vote area
        context = {"noticia": noticia, "user": request.user}
        return render(request, "noticias/vote_area.html", context)


class NoticiaCreateView(FormView):  # NOT LoginRequiredMixin
    template_name = "noticias/timeline_fragment.html"
    form_class = NoticiaForm
    success_url = reverse_lazy("timeline")

    def form_valid(self, form):
        enlace = form.cleaned_data.get('enlace')
        vote = form.cleaned_data.get('opinion')

        # Get or create noticia
        noticia, created = Noticia.objects.get_or_create(
            enlace=enlace,
            defaults={
                'agregado_por': request.user if request.user.is_authenticated else None
            }
        )

        # Fetch metadata
        if created or not noticia.meta_titulo:
            noticia.update_title_image_from_original_url()

        # Create vote (anonymous or authenticated)
        if request.user.is_authenticated:
            voter_kwargs = {'usuario': request.user}
        else:
            if not request.session.session_key:
                request.session.create()
            voter_kwargs = {'session_key': request.session.session_key}

        Voto.objects.update_or_create(
            noticia=noticia,
            **voter_kwargs,
            defaults={'opinion': vote}
        )

        # HTMX response...
        # (rest stays the same)
```

### Step 3: Update Templates

**File:** `core/templates/noticias/vote_area.html`

```html
<div id="vote-area-{{ noticia.pk }}" class="vote-section">
  {% if user.is_authenticated %}
    {% with user_vote=noticia.votos.filter_by_user|first %}
      <!-- Show vote buttons with current vote highlighted -->
    {% endwith %}
  {% else %}
    {% with session_vote=noticia.votos.filter_by_session|first %}
      <!-- Show vote buttons with session vote highlighted -->
    {% endwith %}
  {% endif %}

  <!-- Vote counts -->
  <div class="vote-stats">
    <span>😊 {{ noticia.votos.filter|opinion_count:"buena" }}</span>
    <span>😞 {{ noticia.votos.filter|opinion_count:"mala" }}</span>
    <span>😐 {{ noticia.votos.filter|opinion_count:"neutral" }}</span>
  </div>

  {% if not user.is_authenticated %}
    <div class="auth-prompt">
      <small>
        💡 <a href="{% url 'account_signup' %}">Create free account</a> to sync votes across devices
      </small>
    </div>
  {% endif %}
</div>
```

**Add template filters:**
```python
# core/templatetags/vote_filters.py
from django import template

register = template.Library()

@register.filter
def filter_by_user(votes, user):
    """Get vote by authenticated user."""
    if user.is_authenticated:
        return votes.filter(usuario=user)
    return votes.none()

@register.filter
def filter_by_session(votes, request):
    """Get vote by session key."""
    if request.session.session_key:
        return votes.filter(session_key=request.session.session_key)
    return votes.none()

@register.filter
def opinion_count(votes, opinion):
    """Count votes by opinion type."""
    return votes.filter(opinion=opinion).count()
```

### Step 4: Add Claim Votes Flow

**File:** `core/views.py`

```python
from django.contrib import messages
from allauth.account.signals import user_signed_up

@receiver(user_signed_up)
def claim_anonymous_votes_on_signup(sender, request, user, **kwargs):
    """
    After user signs up, migrate their anonymous votes to account.
    """
    if request.session.session_key:
        anonymous_votes = Voto.objects.filter(
            session_key=request.session.session_key,
            usuario__isnull=True
        )

        claimed = 0
        for vote in anonymous_votes:
            # Check for existing user vote
            if not Voto.objects.filter(usuario=user, noticia=vote.noticia).exists():
                vote.usuario = user
                vote.session_key = None
                vote.save()
                claimed += 1
            else:
                vote.delete()  # User already voted as logged-in

        if claimed > 0:
            messages.success(request, f"✅ Claimed {claimed} of your anonymous votes!")
```

**File:** `core/signals.py` (new file)
```python
from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        import core.views  # Import to register signals
```

### Step 5: Update Noticia Model

**File:** `core/models.py`

```python
class Noticia(models.Model):
    enlace = models.URLField(unique=True)
    meta_titulo = models.CharField(max_length=255, blank=True)
    meta_imagen = models.URLField(blank=True)
    meta_description = models.TextField(blank=True)
    fecha_agregado = models.DateTimeField(auto_now_add=True)

    # Make agregado_por optional (anonymous submissions)
    agregado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,  # Keep noticia if user deleted
        null=True,
        blank=True
    )

    # ... rest stays the same ...
```

---

## Extension Integration

**How anonymous auth works with extension:**

```javascript
// popup.js (browser extension)
document.querySelectorAll('.vote-btn').forEach(btn => {
  btn.addEventListener('click', async () => {
    const vote = btn.dataset.vote;
    const article = await captureArticle();

    // Send to API - browser will include session cookie automatically
    const response = await fetch('https://memoria.uy/api/extension/submit', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      credentials: 'include',  // IMPORTANT: Send cookies
      body: JSON.stringify({...article, vote})
    });

    // Django receives request with session cookie
    // Creates vote tied to session_key (no login needed!)
  });
});
```

**Django CORS config:**
```python
# settings.py
CORS_ALLOW_CREDENTIALS = True  # Allow cookies in CORS requests
CORS_ALLOWED_ORIGINS = [
    "chrome-extension://your-extension-id",
    "moz-extension://your-firefox-id",
]

SESSION_COOKIE_SAMESITE = 'None'  # Required for cross-origin cookies
SESSION_COOKIE_SECURE = True  # Only in production (HTTPS)
```

---

## Privacy Considerations

### What We Store (Anonymous)
- ✅ Session ID (random, not personally identifiable)
- ✅ Vote opinion (buena/mala/neutral)
- ✅ Timestamp
- ❌ No IP address
- ❌ No user agent
- ❌ No device fingerprint
- ❌ No personal data

### What We Store (Authenticated)
- ✅ Email (for login only, never shared)
- ✅ Username (chosen by user)
- ✅ Vote history
- ❌ No social connections
- ❌ No tracking pixels
- ❌ No third-party analytics

### Data Retention
- Anonymous votes: Keep forever (no PII)
- Deleted accounts: Delete all votes + email
- Session votes: Keep even after session expires (for clustering data)

### Clustering Privacy
- Users identified by: "User ABC123" (hashed session ID)
- Cluster visualization: "You are in the green cluster"
- No way to de-anonymize: Session IDs rotated periodically

---

## UX Flow Examples

### First-Time Visitor (Web)
1. Lands on homepage → Sees timeline of news
2. Clicks "😊 Good" on an article → Vote registered instantly
3. Sees: "💡 Create free account to sync votes across devices"
4. Can keep voting anonymously OR sign up

### First-Time Visitor (Extension)
1. Installs extension → No login prompt
2. Clicks extension on news article → Vote buttons appear
3. Votes → Sent to API with session cookie
4. Later visits website → Sees option to "claim" extension votes

### Returning Anonymous User
1. Comes back to site (same browser)
2. Sees their previous votes highlighted
3. Can filter by "My Votes"
4. Eventually prompted: "You've voted 20 times! Want to save across devices?"

### User Who Signs Up
1. Creates account (email + password OR Google)
2. All anonymous votes migrated automatically
3. Can now vote from phone, desktop, extension
4. All votes synced

---

## Migration Path

### From Current DB (With Required Login)

```python
# Migration file: core/migrations/0XXX_anonymous_votes.py

from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ('core', '0XXX_previous_migration'),
    ]

    operations = [
        # 1. Make usuario nullable
        migrations.AlterField(
            model_name='voto',
            name='usuario',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to='auth.user'
            ),
        ),

        # 2. Add session_key field
        migrations.AddField(
            model_name='voto',
            name='session_key',
            field=models.CharField(
                blank=True,
                db_index=True,
                max_length=40,
                null=True
            ),
        ),

        # 3. Remove old unique_together
        migrations.AlterUniqueTogether(
            name='voto',
            unique_together=set(),
        ),

        # 4. Add new constraints
        migrations.AddConstraint(
            model_name='voto',
            constraint=models.UniqueConstraint(
                condition=models.Q(usuario__isnull=False),
                fields=('usuario', 'noticia'),
                name='unique_user_vote'
            ),
        ),
        migrations.AddConstraint(
            model_name='voto',
            constraint=models.UniqueConstraint(
                condition=models.Q(session_key__isnull=False),
                fields=('session_key', 'noticia'),
                name='unique_session_vote'
            ),
        ),

        # 5. Same for Noticia.agregado_por
        migrations.AlterField(
            model_name='noticia',
            name='agregado_por',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='auth.user'
            ),
        ),
    ]
```

**Existing votes preserved:** All current votes have `usuario` set, so they remain tied to accounts.

---

## Testing Plan

### Anonymous User Tests
```python
# core/tests/test_anonymous_voting.py
import pytest
from django.test import Client
from core.models import Noticia, Voto

@pytest.mark.django_db
def test_anonymous_vote():
    """Anonymous user can vote without login."""
    client = Client()
    noticia = Noticia.objects.create(enlace="https://example.com/news")

    response = client.post(f'/vote/{noticia.pk}/', {'opinion': 'buena'})

    assert response.status_code == 200
    assert Voto.objects.filter(noticia=noticia, opinion='buena').exists()

    vote = Voto.objects.get(noticia=noticia)
    assert vote.usuario is None
    assert vote.session_key is not None

@pytest.mark.django_db
def test_anonymous_vote_persists_across_requests():
    """Anonymous votes persist with same session."""
    client = Client()
    noticia = Noticia.objects.create(enlace="https://example.com/news")

    # First vote
    client.post(f'/vote/{noticia.pk}/', {'opinion': 'buena'})

    # Change vote (same session)
    client.post(f'/vote/{noticia.pk}/', {'opinion': 'mala'})

    # Should have 1 vote (updated, not duplicated)
    assert Voto.objects.filter(session_key=client.session.session_key).count() == 1
    assert Voto.objects.get(session_key=client.session.session_key).opinion == 'mala'

@pytest.mark.django_db
def test_claim_anonymous_votes_on_signup(user):
    """Anonymous votes migrated to account after signup."""
    client = Client()
    noticia = Noticia.objects.create(enlace="https://example.com/news")

    # Vote anonymously
    client.post(f'/vote/{noticia.pk}/', {'opinion': 'buena'})
    session_key = client.session.session_key

    # Sign up (simulate)
    client.force_login(user)
    from core.views import claim_anonymous_votes_on_signup
    # Trigger claim (would normally happen via signal)
    # ... test claim logic ...

    # Vote should now be tied to user
    vote = Voto.objects.get(noticia=noticia)
    assert vote.usuario == user
    assert vote.session_key is None
```

---

## Rollout Plan

### Week 1: Anonymous Voting
- Implement model changes
- Update views (remove LoginRequiredMixin)
- Test locally
- Deploy

**Result:** Anyone can vote instantly

### Week 2: Account Creation UX
- Add "claim votes" flow
- Design signup prompt ("Sync across devices")
- Test migration of anonymous → auth votes

**Result:** Users have reason to create accounts

### Week 3: Extension Integration
- Update extension to use session cookies
- Test cross-origin cookie auth
- Add CORS config

**Result:** Extension works without login

---

## Future Enhancements

### Smart Prompts
- After 5 votes: "💡 Sign up to save your votes"
- After 10 votes: "🎯 You've voted on 10 articles! Create account?"
- After using extension: "📱 Access your votes on web too"

### Guest Accounts
- Auto-create lightweight accounts
- User can "claim" later with email
- No password until claimed

### Device Recognition
- Privacy-respecting fingerprinting
- Recognize returning users across sessions
- Offer to "link devices" without forcing login

---

## Open Questions

1. **Session expiry:** How long to keep sessions alive?
   - Proposal: 1 year (Django default: 2 weeks)
   - Rationale: Want anonymous users to keep votes long-term

2. **Vote migration conflicts:** What if anonymous user voted, then signs up and already voted as logged-in user?
   - Proposal: Keep logged-in vote, discard anonymous
   - Rationale: Logged-in vote is more intentional

3. **Spam prevention:** How to prevent one person making many sessions?
   - Proposal: Rate limit by IP (10 votes/hour per IP)
   - Later: Captcha if suspicious pattern

4. **Clustering with mixed auth:** How to cluster users + sessions?
   - Proposal: Treat sessions as "users" in clustering algorithm
   - Sessions are stable identifiers, work same as user IDs

---

**Status:** Ready to implement
**Estimated Time:** 3-4 hours (models + views + tests)
**Impact:** HIGH - Removes biggest friction point
