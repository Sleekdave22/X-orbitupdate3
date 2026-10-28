# Header, Search and saved appearance — version 37

The approved header layout is shared by Chat, Play and Plaza: Back immediately before the title, the navigation menu at the far right, and the existing Play / Chat / Plaza strip at its version 36 coordinates. Chat now has a collapsed Search panel below the strip, matching Plaza's arrangement. The original account search form and handlers remain intact. Conversation search remains available inside individual chats.

Saved account colours and dark/light mode are applied synchronously before stylesheets and page content paint. Android supplies its persisted account palette directly to embedded pages; transparent page backgrounds reveal the already themed native background. No preference request is needed for the first paint. Account changes continue to use account-scoped caches.

## Changes and compatibility

- Updated native header/search presentation, page headers, shared navigation styles and appearance bootstrap.
- Preserved existing routes, forms, captions, authentication, data and GuardianLab protection.
- Kept profile and notification controls. No database migration or backend contract changes.
- Phone contacts, verified phone linking and a Contacts tab remain on hold.
- Original X-Orbit checkout remains clean and unchanged.

## Actual validation

- Android debug build succeeded; 23 JVM tests passed.
- All 38 JavaScript regression scripts passed, including new pre-paint browser/native palette checks, account isolation, HTML script ordering and Search wrapper checks.
- All 70 interface manifest hashes verified; all 53 bundled comparison-web assets match source bytes.
- Browser checks used isolated synthetic accounts: saved Green/Pink colours, collapsed/expanded Chat Search, exact account search, Back, Plaza and Play navigation. Existing form drafts survived search and Back. Header positions and far-right menus were visually checked.
- No live messages, posts or uploads were created. Existing backend regression results from version 36 remain recorded; no backend code changed here.
- Physical S21 first-paint and header confirmation remains pending the user’s manual check.

## Manual check

Reopen X_ORBIT, switch between Chat, Play and Plaza, and confirm the selected appearance is visible immediately. In Chat, open Search below the three module tabs and check Back/menu placement. Search within an individual conversation should still work.

## Deployment

- Implementation commit: 8d05b81a5a66542dfd0bffcbfad13bfcb1163c32; pushed to feature/vibe-timed-navigation in Sleekdave22/X-orbitupdate.
- Both https://localhost:8766/ and https://localhost:8768/ serve the same frozen version 37 source; changed appearance, header and search assets were byte-verified on both.
- Consistent private backup completed before restart. Database integrity passed; all 5 accounts, 12 contact records and 203 messages retained. No active call or stream was interrupted.
- S21 installation completed successfully: versionCode 37, versionName 0.37-header-theme. Authenticated checks confirmed @s21, its saved server, navigation, Vibe, Plaza, match and editor-policy endpoints.
- Deployed browser Chat visually checked with its restored account. S21 visual confirmation remains pending.

## Android ordering correction — version 38

The user’s S21 check found Chat’s module tabs below Search. The legacy published-home-order routine was still rearranging the native comparison screen after construction. Version 38 excludes the fixed comparison layout from that legacy ordering routine, matching the existing comparison guard on design refresh. Other build variants keep their original published-order behavior.

Browser version 37 is already correctly ordered; this correction changes Android ordering only and needs no browser restart. A regression contract checks that the comparison guard remains in place. Physical confirmation will follow installation.

Version 38 validation: debug build succeeded; all 38 JavaScript scripts and 23 JVM tests passed; all 70 manifest hashes and 53 bundled web assets verified. The initial build attempt hit a denied system temporary folder; the successful build used the authorized workspace temporary directory. The initial JavaScript launcher used the wrong working directory; the complete successful rerun used GuardianChat.

Version 38 installed successfully on the S21 from commit 752dfbaed170164a8f826e296ddc3bac84ae6a68. The installed version and @s21 account were authenticated and verified; existing server/API checks passed. Both browsers continue on the already-correct version 37 source. Phone visual confirmation of tabs above Search remains pending.

The user subsequently confirmed on the S21: “Yes—tabs above Search”. Native layout order is manually verified. The separate phone first-paint colour-flash check has not yet been explicitly confirmed by the user.
