# X-Orbit engineering review and handoff (working branch `feature/plaza-swipe-tabs`)

Repository worked on: `Sleekdave22/X-orbitupdate3` (copy of X-Orbit). The original GuardianLab repo was not touched.
Written for Android, backend, database, security and infrastructure reviewers. Everything below says whether it was **built and tested**, **built but untested**, or **not done**.

## 1. How the system is put together (verified by reading the code)
- One Python `ThreadingHTTPServer` (`server/server.py`) with SQLite (168 tables). One bearer-token session is shared by Chat, Play, Plaza and Vibe.
- Feature modules are plain Python files called from `server.py`: `market*.py` (Plaza), `gaming.py`/`gamebox_core.py`/`rankings.py` (Play), `vibes.py` (Vibe), `social.py`, `wallet.py` (simulated), `push.py`.
- Web pages: `index.html` (Chat and the swipe shell), `gaming.html`, `market.html`, `vibe.html`. Android: native Kotlin home (`chat/.../MainActivity.kt`), with Play, Plaza and Vibe as web pages in a WebView.
- Isolation: background jobs in `server.py` each run inside their own `try/except`, so a Plaza failure does not stop Chat or Play. The new Demand sweep follows the same pattern.

## 2. Changes made in this session (all tested unless stated)
### Demand and Hot Demand (new, `server/market_demand.py`)
- Buyers post a categorised request (title 3-80 chars, optional details). Requests are grouped by local text matching: lower-casing, accents, stop words, the existing Plaza synonym table, light singularisation, token overlap and a spelling tolerance. No AI service is called.
- Group becomes Hot when **5 distinct accounts** ask (admin range 3-10). One account can never count twice in a group.
- Seller notices: only sellers who turned on Demand alerts and who list in that category; never to the requesters; at most **2 per recipient per rolling day** (admin range 0-10); never twice for the same group; blocked pairs skipped.
- Buyer notices: when a matching active listing exists or appears (background sweep, at most once a minute), each requester is told once per listing.
- Limits: 5 requests per account per day, 20 open per account, retry keys make double taps harmless, requests expire after 60 days.
- Plaza screen: a **Demand** button added to the existing secondary row (nothing moved or renamed); the page holds the request form, "My requests", "Hot Demand on Plaza" and the seller-alerts switch. Tapping a demand notification opens it.
- Admin Studio: a "Demand and Hot Demand" section (threshold and daily cap) with audit reason; admin-only; recorded in `market_admin_audit`. Uses its own settings keys so the existing complete-configuration check is unchanged.
- Tests: `test_market_demand.py` (9 tests): grouping across wording, no inflation, daily cap, hot threshold and one-time notices, two-a-day cap, buyer match once, admin permissions and audit, close, normalisation.
- Android UI for Demand: **not built**. The WebView Plaza page already contains it.

### Security and reliability (`server/server.py`, `test_hardening.py`, 3 tests)
- Confirmed gap: `/register` accepted unlimited invitation-code guesses (only `/login` was throttled). Now 8 failures per address per minute, then 429, and even the right code is refused while throttled.
- Confirmed gap: no ceiling on signed-in POST requests. Added 600 per account per minute (429 beyond). A human never reaches it; one runaway client can no longer flood the server.
- Confirmed leak: the failed-login table only shrank on success. Both it and the new request counter are now pruned.

### Database (`server/market_pilot.py`)
- Confirmed full table scan on `market_listing_meta` by category. Added `market_listing_meta_category(category_id,state)`. Measured on 30,000 rows: selective lookup 1.18 ms to 0.003 ms; broad category listing 2.02 ms to 1.73 ms (small gain; the main benefit is selective lookups and the new Demand seller query). The query plans for messages, sessions, notifications and the Plaza listing join already use indexes.
- No destructive migration; all new tables use `IF NOT EXISTS`.

### Earlier in the same branch
Swipe shell (Play | Chat | Plaza), Plaza rename, borderless bell and expanding panel, open-from-icon animation, My Orbit rename, Vibe layout and Vibe privacy (viewer blocking and hiding, server enforced, `test_vibe_privacy.py`). Removed `test_rating.py`, which tested four functions no longer in the app.

## 3. Not done, and why
| Item | Status |
|---|---|
| Phone verification and wallet eligibility rules | **No phone-verification code exists** in this repo (searched for OTP/SMS/phone). It cannot be enforced or preserved; it needs a provider (SMS) and your approval. Wallet stays simulated. |
| Plaza Skills / Expertise and Jobs / Employment | Not present: Plaza has 12 product/service categories only. Adding them changes the catalogue; approval requested. Demand already works with any category added later. |
| Android build and device tests | Android SDK is not available in this cloud workspace; **no Android build or Samsung S21 test was possible**. Web was tested in headless Chromium only. |
| Multi-account tests against a real hosted backend | Tests use several real accounts on one local server instance, not a production backend. |
| Push delivery of Hot Demand | Notices are written to the existing Plaza notification list and flow through the existing push dispatcher; real device push was not tested. |
| Broader security review of uploads/admin endpoints | Spot checks only (login/register, request ceilings, admin guards on new routes). A full review by a security engineer is still needed. |

## 4. Hosting and cost (indicative; verify current provider pricing before deciding)
Assumptions: first launch 5,000 registered accounts, 1,000 daily active, about 20 messages per active user per day, 2 GB of media per month growing, video calls peer-to-peer with a TURN relay for about 15 percent of calls, no live-stream hosting beyond the current relay.
- **Phase 1 (launch):** one VPS with 2-4 vCPU and 4-8 GB RAM, 80-160 GB SSD, plus object storage for media and nightly SQLite backups. Roughly US$25-60 per month. Run behind a reverse proxy with HTTPS. Add a TURN server (self-hosted coturn on the same or a small second VPS, bandwidth is the cost: assume US$10-40 per month). Push needs a Firebase project (free tier).
- **Phase 2 (about 20,000 active users):** move SQLite to PostgreSQL (needs approval; non-trivial migration), two app instances behind a load balancer, managed object storage and CDN for media. Roughly US$150-400 per month.
- **Streaming:** in-app live matches should move to a managed media service when audiences grow; cost scales with viewer-minutes, so set a cap before enabling.
- **Monitoring:** structured logs, uptime checks and error alerts (free to low cost tiers exist). No production deployment or paid service was started.

## 5. Recommended next priorities
1. Decide on phone verification provider and the wallet eligibility rules; then enforce on the backend.
2. Android parity for the swipe tabs, Plaza rename and Demand (see `ANDROID_PARITY_HANDOFF_PLAZA_SWIPE.md`) and a real Android build.
3. Add Skills and Jobs to Plaza if still wanted (category catalogue change).
4. Real-device test with two or more accounts on a hosted test server.
5. Plan SQLite to PostgreSQL before sustained concurrent writes grow; measure first.
