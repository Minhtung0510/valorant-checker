"""
BUG DOCUMENTATION — valorant-checker Python scripts
Updated: 2026-06-09

Legend:
  [FIXED]  = confirmed fixed in this version
  [OPEN]   = still present, not yet fixed
  [DESIGN] = intentional design limitation, not a bug
"""

# ── BUGS FROM USER'S REVIEW ──────────────────────────────────────────────────────

# ─── Bug 1 ───────────────────────────────────────────────────────────────────────
"""
Bug 1 — Multiple Playwright instances crash browser
[FIXED] in auth.py
Cause:  Each account called `async with async_playwright() as p:` which spawns
        a Node.js subprocess + Chromium instance. With concurrency > 1, this
        exhausts memory and crashes.
Fix:    Shared Chromium instance via _get_shared_browser().
        Each account gets its own BrowserContext (isolated cookies/proxy).
"""

# ─── Bug 2 ───────────────────────────────────────────────────────────────────────
"""
Bug 2 — asyncio.as_completed() fires all tasks at once, stagger delay is useless
[FIXED] in main.py
Cause:  `tasks = [coro1, coro2, ...]` + `asyncio.as_completed(tasks)` schedules
        ALL tasks immediately. The delay at the bottom of the loop only fires
        AFTER a task finishes — does nothing to prevent simultaneous burst.
Fix:    _process_one_delayed() staggers start times: await sleep(idx * delay)
        before running _process_one.
"""

# ─── Bug 3 ───────────────────────────────────────────────────────────────────────
"""
Bug 3 — Proxy only used during auth, all subsequent API calls bypass proxy
[FIXED] in main.py + auth.py
Cause:  The main loop used a single shared httpx.AsyncClient (no proxy).
        All wallet/MMR/skins calls went through machine's default IP —
        inconsistent with browser auth IP → Riot flagged as suspicious,
        triggering captcha/rate-limit.
Fix:    Each account creates its own httpx.AsyncClient with its proxy:
          async with httpx.AsyncClient(proxies={"http://": proxy, "https://": proxy})
        Also fixed auth.py _headful_login(): entitlements call now uses same proxy.
"""

# ─── Bug 4 ───────────────────────────────────────────────────────────────────────
"""
Bug 4 — Race condition writing accounts.json
[FIXED] in main.py
Cause:  _save_tokens() had no lock. At concurrency=5, 5 accounts read the same
        db dict simultaneously, then write back one-by-one. Last write wins,
        all previous writes are overwritten — tokens of 4 accounts lost.
Fix:    Added _db_lock = asyncio.Lock(). _save_tokens() is now async and
        wraps read-modify-write in `async with _db_lock`.
"""

# ─── Bug 5 ───────────────────────────────────────────────────────────────────────
"""
Bug 5 — _lockfile_tokens() called TWICE per account
[FIXED] in main.py
Cause:  `if _lockfile_tokens():` reads lockfile + spawns subprocess.
        Then `t = _lockfile_tokens()` reads AGAIN. Double syscall per account.
Fix:    `t = _lockfile_tokens(); if t: ...`
"""

# ─── Bug 6 ───────────────────────────────────────────────────────────────────────
"""
Bug 6 — _get_version() created a NEW Lock() on every call
[FIXED] in main.py
Cause:  _http_login() called `_get_version(asyncio.Lock())` — each call got a
        fresh lock, making the cache lock completely useless. Concurrent accounts
        all fetched version simultaneously, hammering valorant-api.com.
Fix:    Module-level `_VERSION_LOCK = asyncio.Lock()`. _get_version() defaults
        to it. Calls simplified to `await _get_version()`.
"""

# ─── Bug 7 ───────────────────────────────────────────────────────────────────────
"""
Bug 7 — accounts.json lockfile/thread safety
[OPEN] in main.py
Note:   _db_lock fixes the write race. Read race (5 accounts reading same db
        dict simultaneously) is low-risk since Python GIL serializes file reads.
        Not worth additional complexity.
"""

# ─── Bug 8 ───────────────────────────────────────────────────────────────────────
"""
Bug 8 — Lockfile returns SAME token for ALL accounts
[DESIGN]
Cause:  Lockfile contains tokens for ONE Riot Client session (one logged-in user).
        If Valorant is running, all concurrent accounts share the same lockfile
        tokens → only one real account gets checked, others fail auth.
Fix:    Use --concurrency 1 when relying on lockfile, OR disable lockfile
        strategy entirely (future enhancement).
"""

# ─── Bug 9 ───────────────────────────────────────────────────────────────────────
"""
Bug 9 — captcha auto-solve dead code in main.py
[OPEN] in main.py
Cause:  _http_login() returns {"_status": "captcha_required"} but main.py
        _process_one() has no handler for this status — captcha_required
        accounts fall through and return generic auth_fail.
Fix:    Add captcha_required to the label_map + error handling in _process_one.
"""

# ─── Bug 10 ──────────────────────────────────────────────────────────────────────
"""
Bug 10 — Screenshot files tracked in git
[FIXED] in .gitignore
Cause:  scripts/python/logs/screenshots/*.png were staged in git.
Fix:    Removed from staging, added to .gitignore.
"""

# ─── Bug 11 ───────────────────────────────────────────────────────────────────────
"""
Bug 11 — Dead code: refresh_token endpoint in Riot RSO flow
[FIXED] in main.py (bug #5 in original doc)
Cause:  Riot RSO (riot-client) does NOT support OAuth refresh_token grants.
        The block calling auth.riotgames.com/token with grant_type=refresh_token
        never worked — dead code that wasted execution time.
Fix:    Removed entire refresh_token block. Expired saved tokens → re-login.
"""
