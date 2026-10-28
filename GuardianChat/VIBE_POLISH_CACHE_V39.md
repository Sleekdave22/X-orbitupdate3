# Vibe badges, stable tabs and reusable media — version 39

Vibe, Chat, Calls and My Orbit keep the existing Chat footer geometry. Its dimensions are set by shared CSS from first paint, without a later content-width measurement. Vibe uses the same icon, label and button metrics. Chat's module layout and Vibe's settings button are present in the initial markup. Native Vibe's duplicate web footer is hidden before paint.

Notification badges use rounded red counters. Native single-digit counters have a minimum square size, centered text and no font padding. Vibe upload counters can extend outside the preview without the parent button clipping them. Icons, label positions, artwork proportions and destinations are retained.

Android's system splash now uses an inset wrapper around the unchanged approved icon, adding 32 dp of transparent padding. Launcher artwork and the in-app intro artwork are unchanged. Physical startup-size confirmation remains pending.

## Reusable public Vibe media

- Account-scoped public photo/video Blob cache: up to 64 MB in memory and 96 MB in local IndexedDB storage. Storage denial or quota failure falls back to memory.
- Each opening makes an authenticated lightweight status request. Valid cached bytes are reused across previous/next, closing/reopening and page reloads. Expired, removed or newly unauthorized content cannot be opened from cache.
- Cache identity includes the media digest and linked-source version. Source changes invalidate generated cards. Live viewer counts and relationships come from the status response.
- Entries use the actual post expiry (12, 24 or 48 hours); bounded storage may evict older entries sooner. Expired records are purged during cache activity. This is not offline playback.
- Private Vibes remain exclusively in the GuardianLab-protected native path and are never placed in this public cache.
- Decoder elements and object URLs are released on close/step. The cache retains media bytes, not video players.
- Existing playback timers, replies, reactions, authorized view receipts and privacy checks remain in place.

The existing status endpoint has additive public metadata and a cache tag. No database migration, ranking, payment, messaging or navigation destination changes.

## Actual checks

- 39 JavaScript regression scripts passed, including memory/persistent reuse, concurrent deduplication, expiry, privacy revocation, source invalidation, account isolation, cache limits and storage fallback.
- 87 related backend test executions passed across Vibes, sources, privacy, viewer handling, navigation state and the new cache contracts.
- Android debug build succeeded; 23 JVM tests passed.
- All 71 interface manifest hashes and 54 bundled web assets verified against source.
- Isolated browser account: all four pages had identical footer bounds (940 × 68), button bounds (229 × 56) and artwork positions at a 1280 × 720 viewport. Repeated Vibe-to-Chat navigation preserved these positions.
- Actual browser badges: Vibe notification 16 × 16 and upload counters 20 × 20, red with rounded corners and visible overflow; visually checked on the icon/preview.
- Existing synthetic image Vibe was opened three times, including after page reload; isolated server tracing recorded one media download with subsequent lightweight authorization requests. Video Blob reuse is covered by automated cache tests. Physical S21 video replay remains a manual check.
- No live messages, Vibes or uploads were created for verification. The original X-Orbit checkout and its approved PNGs remain unchanged.
- Phone-contact work remains on hold.

## Manual check after installation

Reopen X_ORBIT. Check the startup icon, the Vibe notification circle and My Vibe upload counter. Open a public video, move to another Vibe and back, then close/reopen it. Confirm smoother replay and unchanged reactions/replies. Check that Vibe-to-Chat keeps the four bottom tabs aligned.

## Deployment

Implementation commit: 9f8f84ad867d121c949b5299d758cf2df302b093 on feature/vibe-timed-navigation in Sleekdave22/X-orbitupdate.

Both browser addresses serve the same frozen version 39 source. Changed assets, including the cache and navigation scripts, were byte-verified on both addresses. The initial probe ran before startup completed; the successful follow-up verified both running servers.

A consistent private backup was completed before restart. Database integrity passed and all 5 accounts, 12 contact records and 203 messages were retained. No active call or stream was interrupted.

S21 installation completed successfully: versionCode 39, versionName 0.39-vibe-polish. Authenticated checks confirmed @s21, its saved server and the existing navigation, Vibe, Plaza, match and media-editor policy endpoints. User confirmation of physical badge shape, startup size and public-video replay is pending.
