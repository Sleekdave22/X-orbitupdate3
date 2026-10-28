# Simple media editor — version 34

Implemented 27 October 2026 in `Sleekdave22/X-orbitupdate`, branch `feature/vibe-timed-navigation`, following the user's Simple Media Editor handoff. The original `Sleekdave22/X-Orbit` checkout remains clean and unchanged. No navigation destinations, wallpaper, branding, GuardianLab evidence controls, chat/call behavior or financial services are redesigned.

## Behavior and connections

- The shared editor opens directly to a large preview with Back and Done. Photos expose Crop; videos expose Crop, Trim and playback. Done only prepares media and returns it to the existing composer. Captions and audience selections remain in that composer; sending/publishing requires its existing separate action.
- Crop has eight touch handles, dimming, an adjustment grid, image dragging, pinch zoom, and Free/Original/1:1/4:5/9:16 ratios. Cancel, Reset and Apply affect only the current tool. Applied crop and trim remain independent.
- Trim has real video thumbnails, draggable endpoints, excluded-area dimming, scrubbing, a playhead, precise time summary and bounded playback. The actual export uses the selected crop and start/end times, preserves orientation and resamples audio with synchronized timestamps.
- Back prompts for Discard changes or Keep editing only when edits changed. Android Back also honors the editor. Preparing blocks duplicate submissions; failed jobs retain edits for retry. Cancellation stops a running export and keeps its private original available.
- Vibe camera/file selection now enters the editor. Approved video duration is 60 seconds per Vibe; longer selections export contiguous segments for review/removal before explicit publication. Each published segment retains its own expiration, visibility, audience and retry identity. Photos still display for ten seconds. Video viewing uses actual edited duration on browser and Android.
- Plaza's existing photo picker now enters the same Crop editor and returns photographs to the existing listing form. Product-photo validation, descriptions, prices, delivery and publication actions are retained. Mixed video listing galleries are **not** added in this milestone.
- Unseen Vibe badges now count only connected authors represented in the compact feed, preventing unrelated public posts from leaving an uncleareable badge.

## Data, routes and safeguards

Additive tables: `media_editor_assets`, `media_editor_jobs`, `media_editor_renders`, and `vibe_media_metadata`. Existing user, message, listing, match and Vibe record structures remain compatible; no destructive migration or data rename is required.

Authenticated editor routes: GET `/media-editor/policy`, `/media-editor/original`, `/media-editor/job`, `/media-editor/media`; POST `/media-editor/upload`, `/media-editor/process`, `/media-editor/cancel`. Originals, renders, job state and cancellation are restricted to their owning account and destination. Retry keys cannot replace originals or recipes. `/vibe/publish` accepts an owned, ready Vibe render and copies it into the existing independently expiring post.

The user's source file is never modified. Server-side temporary originals/renders are private and expire after 24 hours; published Vibes retain their separate chosen expiry. Source uploads are bounded to 20 MB, images to 24 megapixels, videos to 3840×2160, with one export at a time, four queued jobs and bounded worker time. Processing runs in a child process with private temporary storage and cleanup. Interrupted jobs become retryable after restart. PyAV, Pillow and NumPy already exist in the runtime; no new hosted service or credentials are required. Evidence verification keeps its separate validator unchanged.

The approved Plaza duration policy defaults to 60 seconds through `ORBIT_PLAZA_VIDEO_SECONDS`; its future video-gallery integration must enforce that policy. This milestone's existing listing picker remains photo-only.

## Actual validation

- **130 backend tests passed** in 185.391 seconds: core server, real media processing, authenticated editor jobs, navigation badges, Vibe activity/privacy/source links, Plaza pilot and listing types.
- **37 JavaScript regression scripts passed**, including shared-editor controls, Crop/Trim independence, pinch/drag, fractional timing, cancel/reset/apply/discard, retry, duplicate preparation, and confirmation that Done does not publish.
- **23 JVM tests passed**; Android debug version 34 built successfully. The packaged browser assets are checked against the final server sources and interface manifest before installation.
- Real generated media tests cover exact photo selection and EXIF orientation; combined video crop/trim; 44.1 kHz audio; high-frame-rate sources; camera WebM with missing duration; between-frame cut boundaries; and a 155-second source exporting 60/60/35-second clips with correct boundary frames and audio timing. A larger-than-pipe-buffer input regression verifies worker completion.
- Read-only browser visual checks used generated photo/video samples with uploads disabled and no account access. Large preview, crop handles/ratios, trim filmstrip and Back/discard states were inspected; dark and bright themes and a 390×620 phone-sized layout were checked.
- The automated browser file-upload test was declined and was not repeated or bypassed. Physical S21 picker → edit → Done → composer verification and browser end-to-end picker verification remain manual acceptance checks after deployment. No live post was published by these visual checks.
- The 13 previously documented legacy rating-test errors are outside this milestone; the full project is not described as production-ready on the strength of these affected tests.

## Changed files and remaining scope

New shared UI: `server/media-editor.js`, `server/media-editor.css`. New processing/services: `server/media_processing.py`, `server/media_editor.py`. Regression tests: `test_media_processing.py`, `test_media_editor.py`, `test_media_editor_ui.js`, plus the Vibe badge regression. Connections: `server.py`, `vibes.py`, `vibe.html/js`, `market.html/js`, `navigation_state.py`. Android: `MainActivity.kt`, `ComparisonAssetPolicy.kt` and its test, version/bundled-asset configuration; updated `phone-interface-manifest.json`.

Remaining consolidated-handoff milestones: mixed Plaza media/cover/gallery storage, storefront/profile and search improvements, and a separate conservative dead-code audit. These are not silently marked complete by this editor update.

Manual check: open Vibe → + → choose a photo/video; adjust Crop (and Trim for video), Apply, then Done. Confirm the caption/audience survive, the composer shows the approved selection and nothing publishes until Publish is pressed. Repeat Crop in Plaza's existing photo picker. Check Android Back, no-change exit, changed-edit discard, retry and audio playback. A source longer than 60 seconds should produce individually removable Vibe segments.

## Deployment evidence

Implementation commit **`5afed99e92c0f6c8e5139ec58da12e83cc9822a7`** was pushed to `origin/feature/vibe-timed-navigation` on 27 October 2026. Both `https://localhost:8766/` and `https://localhost:8768/` now serve the same frozen implementation; new editor and existing module asset bytes were verified against the release. A consistent private SQLite backup preceded the restart. Database integrity passed, with all five users, twelve contacts and 203 messages retained, and additive editor tables present.

Android **version 34, `0.34-shared-media-editor`**, installed successfully on the S21 under the unchanged `com.guardianlab.chat` package. All 53 bundled assets match server sources; all interface-manifest hashes match. Saved @s21 identity and authenticated Vibe, Plaza, match, navigation and 60-second editor-policy APIs were verified without changing the saved server or exposing credentials. Mainfirst's existing browser session still loads its Vibe page. Physical edit/composer acceptance has been requested and remains pending; installation/API checks do not substitute for that observation.

The original X-Orbit checkout remains clean at `bf029cea24983f58022736cb44bbb8c2e18d73ff`. No merge into either repository's `main` branch was performed.
