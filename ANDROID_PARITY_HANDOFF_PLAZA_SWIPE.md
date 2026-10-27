# Handoff for Codex: Android parity for the swipe tabs, Plaza rename and Vibe privacy

Branch with the web work: `feature/plaza-swipe-tabs` on `Sleekdave22/X-orbitupdate3`.
Android was NOT changed or compiled here. Everything below is for you to build in `MainActivity.kt`.
Never touch `Sleekdave22/GuardianLab`. Keep the app icon unchanged (no shield). Protection / view-once logic stays untouched. Admin only for Mainfirst.

## 1. Swipe tabs on the home screen (replace the Orbit Play / Orbit Market buttons)
Web reference: `orbit-shell.js`, `orbit-shell.css`, `orbit-embed.js`.
- One pager (ViewPager2 or a horizontal pager) with three panes in this order: **Play, Chat, Plaza**. Chat is the default.
- One tab row above it: three tabs, each icon then word: Orbit Play icon + "Play", chat icon + "Chat", Plaza icon + "Plaza". Icons: `navigation-icons/chat-icon.svg`, `navigation-icons/orbit-market-icon.svg`, and the existing plain Orbit icon for Play.
- ONE shared underline (a single view, 3px, violet to cyan gradient) that is moved by the pager's scroll offset: `translationX = (position + offset) * tabWidth`. It must follow the finger, not jump on settle.
- The header title follows the pane: "Orbit Play", the chat title, "Orbit Plaza".
- Play and Plaza stay WebViews (`showGaming`) inside their panes. Swipes that start in a WebView must reach the pager (the web version forwards horizontal touch moves with postMessage; on Android use `requestDisallowInterceptTouchEvent` or a JS bridge call).
- Chat rows: swipe-left still deletes (existing). Swipe-right on a row goes to Play.
- Header band for Chat and Play uses the same solid "clean area" as Vibe and Plaza.
- Respect the system animation setting (no animated scroll when animations are off).
- Unread badges for Play and Plaza sit on their tabs (same counts as today).

## 2. Open-from-icon animation
Web reference: `orbit-reveal.js`. Any panel or tab that opens (settings, menus, notification panels, dialogs, My Orbit, Calls) grows as a circle from the button that was pressed (about 360 ms, decelerating). Do not use it for the three main tabs. Skip when animations are disabled.

## 3. Renames (user-visible text only; internal ids, URLs and API paths stay)
Orbit Market -> **Orbit Plaza**, Market -> **Plaza**, Profile -> **My Orbit** (bottom nav label, screen heading, any dialog title). Search strings in `MainActivity.kt` and `strings.xml`.

## 4. Plaza screen
- Page uses the full wallpaper; cards are translucent.
- Notification bell: top right of the page, no box. Outline icon normally; lighter filled icon while its panel is open.
- Tapping the bell opens a panel that grows from the bell down to 50 percent of the screen height, drawn on the Settings wallpaper, with a dim layer behind it. Title "Plaza notifications".

## 5. Vibe
Web reference: `vibe.html`, `vibe.js`, `vibe.css`, `vibes.py`.
- My Vibe is the post thumbnail itself (no "My Vibe" line); a **+** button at the right replaces the camera button.
- The notification bell on Vibe is removed. All Vibes are one list, newest first; viewed Vibes sit below a line break labelled "Viewed".
- Footer / bottom nav last tab is "My Orbit". Vibe header button reads "Orbit Plaza".

## 6. Vibe privacy (server is done and tested)
New endpoints on `/vibe/<action>`:
- GET `privacy` -> `{blocked:[{uid,name}], hidden:[{uid,name}]}`
- POST `viewer_block` / `viewer_unblock` `{target}`: stop (or allow again) someone viewing MY Vibes. Enforced everywhere (feed, preview, media, view, reply).
- POST `hide` / `unhide` `{target}`: remove someone's Vibes from MY list.
- Own posts can be deleted.
UI: a "..." menu on each contact row (Hide their Vibes from my list / Stop them viewing my Vibes) and a Privacy section in Vibe settings listing both groups with undo buttons.

## 7. Not verified
Android build and device behaviour are untested. Web was checked in Chromium at phone size, dark theme, including touch swipes from inside the embedded Play and Plaza pages.
