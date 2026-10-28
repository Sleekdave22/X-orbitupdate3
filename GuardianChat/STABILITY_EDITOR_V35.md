# S21 responsiveness and editor return — version 35

The S21 report after version 34 was a failed acceptance check: slow/unfinished OrbitChat loading, an app close after one or two minutes, dim editor actions, and Done finishing processing without revealing the Vibe composer.

## Evidence and repairs

Android's process-exit history confirms an input-dispatch ANR on 27 October 2026, with approximately 1.4 GB RSS in the app and 1.3 GB in its WebView renderer. Similar ANRs predate version 34. The latest editor job was ready with one 60-second render and no backend error; it was not still transcoding.

Two retention paths were identified in the native UI. Active-Vibe badges recreated SVG WebViews during each navigation update, while a strong list retained every icon WebView until leaving the screen. Contact-row swipe mappings used weak keys but strong values referencing the containing row, retaining the view tree through the map. Rebuilding the contact list also repeatedly decoded full-size avatars.

- The original five supplied SVG assets are now rendered directly with AndroidSVG 1.4 into cached Pictures and lightweight ImageViews. No browser renderer is created for navigation/badge artwork. The cache is restricted to the known five artwork names. Asset bytes, dimensions, positions, actions and accessibility labels are preserved. Dependency and API usage follow the [official AndroidSVG documentation](https://bigbadaboom.github.io/androidsvg/).
- Unchanged badge state is reused. Screen changes clear old navigation targets and swipe mappings; swipe map values are also weak references. Unchanged contact responses no longer rebuild the list. Small avatars use a bounded 24-entry cache of thumbnails with a maximum edge of 128 pixels; full photo viewing retains its existing orientation-aware decoder and size.
- The media editor repaints paused previews only when their visible state changes, including the first decoded frame and scrubbing. Closing or leaving thumbnail generation explicitly unloads the video decoder. Crop/Trim behavior and exported processing are unchanged.
- Apply and Done use filled account-accent buttons and contrasting text. Disabled processing states remain visibly distinct.
- Successful Done now opens, focuses and scrolls directly to the existing Vibe composer. The prepared preview, caption and audience remain available; publication is still a separate explicit action.

## Validation and limits

All 37 JavaScript regression scripts passed. Added regressions verify that Done opens and reveals the composer without publishing, retains caption/audience, keeps the previous prepared draft on cancellation, paints the first decoded video frame, avoids continuous paused redraw and updates after scrubbing. The Android debug build and its 23 JVM tests pass. Final assets/manifest are checked against the APK before deployment.

Read-only browser visual checks with generated media and uploads disabled confirm the video frame, bright Done and bright Apply. No live Vibe was published for these checks. Existing version 34's 130 affected backend tests remain the processing/API baseline; this correction changes no backend Python or database schema. GuardianLab, accounts, notifications, navigation destinations, original repository and real-money restrictions remain unchanged.

Installing an update and checking APIs do not prove that a physical-device ANR is resolved. After installation, the S21 must remain open through repeated polls and navigation for more than two minutes, then complete editor → Done → composer without publishing. Memory/exit diagnostics and the user's observation must be recorded separately. That acceptance check is pending until actually observed.

## Version 35 deployment and observed follow-up

Implementation `bb80b2134ec53a52f1adef224214d5c90f43d4d8` was pushed and deployed to both browser addresses and the S21. @s21 and authenticated APIs were retained. The user confirmed that OrbitChat opens correctly. During a 183-second diagnostic window, the same app PID stayed alive; native Chat reported zero WebViews, and the Vibe page reported one. View counts stayed at 1,297 after navigation, rather than accumulating icon browsers. App RSS settled near 464–466 MB over the final three samples, following a temporary 566 MB sample. No new ANR was recorded; the newest ANR remained the earlier 06:42 event. This is a bounded observation, not a claim of indefinite stability. Physical video edit → Done → composer acceptance remains unconfirmed by the user.
