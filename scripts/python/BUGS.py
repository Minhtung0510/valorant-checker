"""
BUG DOCUMENTATION — auth.py

────────────────────────────────────────────────────────────────────────────────────
BUG #1 — Duplicate lockfile calls (main.py)
  Location: main.py, _get_tokens(), line ~497
  Impact:  Minor (double syscalls)
  Status:  Not fixed
  Detail:  `_lockfile_tokens()` is called TWICE — once to check truthiness,
           once to extract the tokens dict. Each call re-reads the lockfile
           from disk and spawns a subprocess. Should cache the result.

────────────────────────────────────────────────────────────────────────────────────
BUG #2 — Lock file is CLASS-level shared, but a new Lock() is passed per-call
  Location: main.py, _http_login(), line ~290
  Impact:  Version cache is NOT thread-safe
  Status:  Not fixed
  Detail:  `_get_version(asyncio.Lock())` creates a brand-new Lock every time
           _http_login() is called (once per account). The cache lock should be
           module-level, not per-call. Multiple concurrent accounts bypass the
           lock entirely.

────────────────────────────────────────────────────────────────────────────────────
BUG #3 — expires_at type mismatch
  Location: main.py, lockfile_tokens(), line ~271 vs _get_saved_tokens()
  Impact:  Lockfile tokens are never reused
  Status:  Not fixed
  Detail:  lockfile_tokens() returns `expires_at: datetime.now().timestamp() + 3600`
           (a FLOAT). _get_saved_tokens() reads from accounts.json which stores it
           as a JSON number (also float). The comparison at line ~512:
             `expires_at > datetime.now().timestamp() + 120`
           compares float to float. This works. BUT: if ANY account has
           `expires_at` stored as an INTEGER string in accounts.json (from manual
           edit or old version), the comparison silently fails and token is
           treated as expired. Low risk in practice.

────────────────────────────────────────────────────────────────────────────────────
BUG #5 — Token refresh uses WRONG endpoint
  Location: main.py, _get_tokens(), Strategy 2 refresh, line ~533
  Impact:  Refresh token strategy never works
  Status:  Not fixed — by design (Riot RSO doesn't support refresh_token grant)
  Detail:  Riot's RSO (Riot Sign-On) does NOT issue OAuth refresh tokens.
           The `riot-client` flow uses a session-based cookie approach.
           Sending a refresh_token grant to auth.riotgames.com/token returns
           400 or empty response. This code path is dead code.

────────────────────────────────────────────────────────────────────────────────────
BUG #6 — Captcha auto-solve token injection uses WRONG selector (HISTORICAL)
  Location: auth.py (old code), _headful_login()
  Impact:  hCaptcha tokens were never injected correctly
  Status:  FIXED in this version
  Detail:  OLD code: `document.querySelector("[name=g-recaptcha-response]")`
           This targets Google's reCaptcha, NOT hCaptcha.
           hCaptcha uses `name="h-captcha-response"` and/or
           `data-hcaptcha-response` attribute.
           FIXED: now sets both `name="h-captcha-response"` value attribute
           AND `data-hcaptcha-response` attribute.

────────────────────────────────────────────────────────────────────────────────────
BUG #7 — Sitekey detection only searched parent page (HISTORICAL)
  Location: auth.py, _is_hcaptcha_on_page()
  Impact:  hCaptcha sitekey was often not found → captcha solver skipped
  Status:  FIXED in this version
  Detail:  OLD code only searched `body_html` (parent page) for sitekey.
           hCaptcha's sitekey is embedded inside the iframe's `src` URL
           (e.g. `https://js.hcaptcha.com/.../?sitekey=XXXXXX...`).
           FIXED: now also iterates `page.frames` and extracts sitekey from
           each frame's URL.

────────────────────────────────────────────────────────────────────────────────────
BUG #8 — Captcha submit button click was unreliable (HISTORICAL)
  Location: auth.py, _headful_login(), after token injection
  Impact:  Token was injected but form never submitted
  Status:  FIXED in this version
  Detail:  OLD code tried `query_selector` on the main page for buttons,
           which doesn't find buttons inside the hCaptcha iframe shadow DOM.
           FIXED: now iterates ALL frames (including iframe) and searches
           for submit buttons inside each frame before falling back.

────────────────────────────────────────────────────────────────────────────────────
BUG #9 — Lockfile strategy returns SAME token for ALL accounts
  Location: main.py, _get_tokens(), Strategy 1
  Impact:  Multiple accounts sharing one lockfile get the same puuid/access_token
  Status:  Not fixed — inherent to how lockfile works
  Detail:  The lockfile contains tokens for ONE Riot Client session (one logged-in
           user). If Valorant/Riot Client is running, all accounts processed
           concurrently will use the SAME token — meaning only ONE real account
           gets checked, others fail auth. Only safe with concurrency=1.

────────────────────────────────────────────────────────────────────────────────────
BUG #10 — Windows playwright crash from Linux-optimized flags (HISTORICAL)
  Location: auth.py, _headful_login(), launch_args
  Impact:  Browser crashed instantly on Windows before user could see anything
  Status:  FIXED in this version
  Detail:  OLD launch args included: --no-zygote, --disable-dev-shm-usage,
           --disable-gpu, --disable-background-networking, --disable-crash-reporter,
           --disable-hang-monitor, --disable-domain-reliability.
           These flags are Linux/Docker optimizations that cause Chromium to
           crash on Windows. FIXED: only kept 4 safe flags for Windows.

────────────────────────────────────────────────────────────────────────────────────
"""

# ── Remaining code below is the actual implementation ─────────────────────────────
