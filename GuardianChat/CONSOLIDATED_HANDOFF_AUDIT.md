# Consolidated handoff audit

Inspected 26 October 2026 against the supplied consolidated handoff. Active repository: `Sleekdave22/X-orbitupdate`, branch `feature/vibe-timed-navigation`, implementation baseline `9c7e1a386b1ec22928b5e2f806b674901f67e163`. GitHub confirms the same branch SHA; default `main` remains `3b1209ef0ffc554981f3e8035a444a39d6014a37`. The original `Sleekdave22/X-Orbit` checkout remains unchanged at `bf029cea24983f58022736cb44bbb8c2e18d73ff`.

## Existing functionality and reuse

- Android's existing origin-checked WebView file chooser already permits multiple image/video selections. Reuse this rather than introducing a second Android picker, identity or login.
- Vibe publication, explicit private audiences, exclusions/muting, expiration, per-post views, retries, segmented rings, viewer identity, reactions and replies already have real backend contracts. Extend these records and handlers. Existing publication currently stores validated original media directly in SQLite and has no editing stage.
- The Vibe camera uses the shared evidence capture component in a separate Vibe mode. Preserve dispute capture rules and GuardianLab protection. Current Vibe recording/playback uses 20 seconds; this handoff explicitly changes video Vibes to a maximum of 60 seconds per segment. Photos retain their existing ten-second display.
- Plaza supports Products, Services, Skills and Jobs with conditional prices/salaries and distinct fields. `market_listing_types.py` and `market-types.js` are the shared rules; preserve them.
- `market_pilot.py` supports up to six normalized JPEG photographs per listing through `market_images`, ordered by position. No listing videos, media editor, mixed gallery or cover selection exist yet.
- `market_search.py` already searches individual listing titles, descriptions, category/subcategory, attributes and type details using case-insensitive tokens, weighted relevance and safe location/price filters. It queries current eligible rows directly, so edits do not require rebuilding a separate index. Keep this engine and strengthen integration tests rather than adding an AI dependency.
- `/market/store` and the listing detail's Storefront action already browse an owner's listings. Add profile access and sensible empty storefronts for accounts without a registered shop, preserving established navigation.
- The shared Play/Chat/Plaza strip, existing account theme tokens, buttons, spacing, cards and transitions are the design source. Orbit Play and its match/ranking services are outside implementation changes.

## Conflicts and infrastructure limits

Vibe currently calls `result_reviews.video_probe`, whose evidence-specific requirements assume at least three seconds and approximately 60 seconds maximum. A reusable editor needs a separate media validation/export module; changing that validator would risk dispute evidence. PyAV 16.1.0, H.264 and AAC encoders are already available in the server runtime. No new hosted AI service or object-storage provider is configured.

Existing HTTP uploads are JSON/base64, files are whole blobs, and images use SQLite. Large video originals, simultaneous transcodes and repeated exports can grow memory/database usage. Add bounded processing, private originals, cancellation, retry identity, expiry and cleanup before extending gallery uploads. Keep technical byte/resource limits explicit; do not present them as a finalized Plaza duration policy. Plaza's video maximum remains an unresolved product decision, configurable without imposing a silent three- or five-minute limit.

One audit correction is needed in the new Vibe badge: only posts represented in the user's contact/following feed should contribute to unseen counts. Otherwise unrelated public authors could leave a count that the compact feed cannot clear. Retain account permissions, views and privacy filtering.

## Integration plan

1. Record the version 33 deployment and this audit separately from feature implementation.
2. Add a destination-configured shared editor with original preservation, trim/split/crop/rotation, preview/review, processing progress, cancellation and idempotent retry. Vibe segments use a 60-second maximum with contiguous boundaries, independent publication/expiration and explicit segment review/removal. Integrate browser and Android WebView flows, then test before deployment.
3. Extend listing media additively, retaining all legacy image IDs/routes and existing photo-only listings. Add ordered photo/video metadata and cover references, authorized reads, thumbnails and lazy detail playback. Reuse the shared editor without Vibe splitting.
4. Reuse lexical listing search and storefront routes. Add profile access and cross-account publish/edit/unpublish/search checks with all four listing types.
5. Perform a separate conservative dead-code audit. Trace scripts, route dispatch, WebView bridges, native callbacks, background jobs and feature flags. Remove only proven dead code in its own commit; retain uncertain, planned and backward-compatible paths.

## Baseline and verification gates

Version 33 passed 87 real HTTP/database backend tests, 36 JavaScript regression scripts and 23 JVM tests; the APK's 51 bundled assets match server sources. Both live browser addresses serve the frozen source; @s21 and Mainfirst are retained. Native installation and authenticated API access were verified. Physical editor/camera interactions will require separate device verification after implementation.

The previously documented 13 legacy rating-test errors reproduce against unchanged version 31 and remain outside this handoff. Never classify those tests or untested media features as production-ready. Synthetic tests, isolated multi-account HTTP checks and physical-device observations must be reported separately. Feature and cleanup commits remain separate, with targeted rollback and preservation of the original repository.

## 27 October clarification and editor milestone

The user approved **60 seconds for video**. Vibe exports therefore split into contiguous segments of at most 60 seconds; the shared Plaza policy defaults to 60 seconds without splitting. The later Simple Media Editor handoff supersedes the proposed editor controls: implement Crop/Trim with Back/Done, leaving publication in the composer. The existing Plaza photo picker gains Crop; mixed photo/video listing galleries remain the next separate milestone. See `SIMPLE_MEDIA_EDITOR_UPDATE.md` for implemented scope, actual verification and remaining checks.
