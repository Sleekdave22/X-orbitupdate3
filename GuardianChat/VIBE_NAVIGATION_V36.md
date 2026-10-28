# Vibe controls, account colours and shared navigation — version 36

Requested follow-ups to the version 35 stability repair, implemented in `Sleekdave22/X-orbitupdate` on 27 October 2026. The original X-Orbit repository remains unchanged. The user explicitly put phone contacts and optional phone verification on hold; neither is implemented or accessed here, and no new Contacts tab or permission is added.

## Implemented behavior

- Four bottom tabs retain their order and destinations. Vibe now has its visible label. Notification counts attach to the icon artwork, rather than the surrounding tab. Artwork alone is horizontally scaled by 1.08; icon height, tab-box dimensions and label size are unchanged.
- Public and protected native Private Vibes have invisible media tap regions: left 35% previous, centre 30% pause/play, right 35% next. Downward dismissal remains available. The browser's lower Previous/Next buttons and built-in video controls are removed. Existing segmented progress indicators and accessible keyboard navigation remain.
- The media stage extends to the reply line. Caption, follow/source actions, reactions and owner viewer controls float over the media. The reply box remains below it and still sends a private Vibe-linked reply through the existing service. GuardianLab still protects the native Private Vibe stage and surrounding content; no protection rule is reduced.
- Authors see the current unique-view count and can open the existing identity/timestamp/reaction viewer list. New media-response fields provide `previous_id` and an author-only `view_count`; existing `next_id` remains compatible. Previous/next references only include posts that the requesting account is permitted to view. Other viewers cannot inspect author-only viewer records.
- Contact Vibe rows have compact dividing lines and reduced padding, preserving the distinction between viewed and new posts.
- Selected controls, primary actions and Chat Search now use the account's sent colour and matching contrast text. Inactive controls use a faded received colour. Fixed-purple overrides in the relevant shared button rules and native Search style are removed; ordinary body text and status colours retain their existing values.
- The Chat/Play/Plaza selectors share fixed browser coordinates and equal dimensions, outside the animated page content. Static destination markup is reused instead of duplicated. Native Chat, Play and Plaza share the same native header/module-strip dimensions; WebView content occupies the remaining width without a duplicate selector. Existing profile, notification, settings, Back and module actions remain connected.
- The Play page's repeated play-for-play/pay slogan is removed from its header. The intro retains the wording.

## Actual checks

- 54 affected backend tests passed, covering Vibe activity, private audiences and source integrations. Added coverage verifies author-only counts and that private previous/next references skip posts hidden from the requester. No database migration is required.
- All 37 JavaScript regression scripts passed. Coverage includes four ordered labelled tabs, icon asset parity, artwork-attached badges, tap versus drag/cancel behavior, playback clocks, viewer reply/privacy behavior, account-scoped themes and the existing editor/composer return checks.
- Android debug build and 23 JVM tests passed. Final packaged assets and manifest are checked byte-for-byte before installation.
- Isolated browser QA used generated sample media and synthetic accounts on a separate local database. No personal files were selected or uploaded. The right tap advanced to the video, centre tap paused it with native video controls absent, and left tap returned to the previous post. Floating controls, the separate reply line, compact list, Vibe label and icon badge were visually inspected.
- At a 1280-pixel viewport, Chat, Play and Plaza selectors all measured `[9,76,418,42]`, `[431,76,418,42]`, `[853,76,418,42]` for x/y/width/height. Their shared strip remains outside page animations.
- Using the synthetic account's Green/Pink choice, Chat Search, the selected module and Play Home/Plaza Browse computed to `rgb(29,113,72)`. Inactive Plaza controls used the faded received colour; body text remained `rgb(241,245,249)`. Real accounts' saved choices were not changed.

## Acceptance and remaining scope

Version 35's physical three-minute stability observation is recorded separately. New native tap/overlay geometry and appearance require a device check after version 36 installation. Broader mixed Plaza galleries/storefront work remains a separate consolidated-handoff milestone. Phone contact discovery and verification remain on hold at the user's request.

## Deployed version

Implementation commit `3e7b3670d9c44001bb0c6bbe0deffd581638f669` is pushed to `origin/feature/vibe-timed-navigation`. On 27 October 2026 both `https://localhost:8766/` and `https://localhost:8768/` were restarted on the same frozen version 36 source. Shared SQLite integrity and retained counts passed: five users, twelve contacts and 203 messages. A consistent private backup preceded deployment. New and existing asset bytes were checked against the release.

S21 package `com.guardianlab.chat` updated successfully to version 36, `0.36-vibe-navigation`. All 53 packaged assets match server sources and the interface manifest matches. @s21 and its saved server/account were retained; authenticated navigation, Vibe, Plaza, match and editor-policy APIs passed. The live browser Vibe page loads the existing Mainfirst session. The final physical-device check has been requested and remains pending; no live Vibe or message was published to test it.

The original X-Orbit checkout remains clean at `bf029cea24983f58022736cb44bbb8c2e18d73ff`. Neither repository's main branch was merged.
