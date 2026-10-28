# OrbitPlaza, shared navigation and Vibe update

Working repository: `Sleekdave22/X-orbitupdate`, branch `feature/vibe-timed-navigation`, based on `647ed06f308fdf67e69db8c269fff1176b2226db`. The original `Sleekdave22/X-Orbit` checkout is separate. GitHub main was inspected at `3b1209ef0ffc554981f3e8035a444a39d6014a37`; this update is delivered on its feature branch, without merging main.

## Existing systems reused

Shop ownership, advert IDs, category catalog, currencies, lexical discovery, saved listings, listing revisions, moderation, inquiries, existing Chat conversations, notifications, Vibe sharing and the labelled demo ledger remain in place. The four listing types extend these contracts rather than introducing separate marketplaces. Existing `/market/*` APIs and links remain valid; visible branding is OrbitPlaza. The own-account destination is My Orbit.

## Implemented changes

- Product, Service, Skill and Job adverts use conditional fields and server-side validation on creation and editing. Products retain photographs, condition and delivery rules. Services and skills support optional pricing modes; jobs support undisclosed, negotiable, fixed and ranged salaries. Missing amounts remain NULL, with an empty legacy display field, never an invented zero.
- Service/skill quotation requests and professional/job inquiries reuse existing authorized Chat connections and one listing notification. Job websites require valid external HTTPS links; opening a website or conversation does not claim a formal application. Deadlines stop new job inquiries. Product reservations/offers and demo orders cannot be started for services, skills or jobs.
- Compact title/location/italic-handle cards retain full detail pages. Search, refinement and categories collapse. Type, country/locality, optional distance, price/salary bounds and low/high sorting extend existing search. Mixed-currency price sorting requires a currency. Price-free adverts remain discoverable and sort after priced adverts.
- Optional advert/search coordinates are rounded to two decimal places. Distance is approximate; country/locality search works without location access. Android requests only coarse location, only after the explicit location action. Unknown locations never produce invented distances.
- Authenticated unread-message badges and authorized Vibe indicators appear on navigation/profile photos. Existing bottom Vibe, Chat, Calls and My Orbit destinations remain intact.
- Play, Chat and Plaza use their supplied icons and one shared line that follows horizontal dragging on the top strip. Module changes retain original routes and handlers. Chat-row reply/delete gestures remain unchanged. Local tab/detail openings use short transitions and respect reduced-motion preferences.
- Plaza has a transparent top-right bell and an animated panel occupying half the viewport, using the existing settings artwork. Notification read/open behavior remains account/category scoped. Settings reuse the existing account settings; the wider side menus keep identity content left aligned.
- Selected tabs follow the account's sent-message colour; inactive tabs use faded received-message colour. Wallpaper sketches are softened with rendering layers. Original PNG/SVG artwork remains unchanged; body text and unrelated actions are not globally recoloured.
- Vibe photos display for ten visible seconds, videos for twenty, with increasing progress. Replying, backgrounding, buffering and protected-view shielding pause the clock. Partial downward dragging/flicks dismiss the viewer. Only the own-post preview opens My Vibe; the adjacent plus offers photo, video or file selection.
- Vibe lists sort recent posts first, with viewed groups beneath a divider. The Vibe bell is removed. Settings support everyone/contacts/accepted-followers for Public Vibes, excluded viewers and muted authors. Account search can add non-contacts to privacy lists. Exclusion is enforced for current/future public/private media, previews, direct links, status, view receipts, reactions and new replies. Muting affects the viewer's feed only. Private audiences and GuardianLab restrictions remain enforced. Public content already viewed or copied cannot be recalled.

## Backward-compatible storage changes

`market_listing_meta` gains `listing_type` (PRODUCT default), `pricing_mode`, `type_details`, and nullable approximate latitude/longitude. Existing IDs, owners, prices, images and saves are retained. `vibe_privacy` and `vibe_visibility_rules` store account settings. Migrations are repeatable. No financial, ranking, matchmaking, message or protected-key structures are renamed.

## Files and validation

Backend additions: `market_listing_types.py`, `market_location.py`, `navigation_state.py`, `vibe_privacy.py`. Existing listing, discovery, inquiry, Vibe and server dispatch modules are extended. Browser changes are confined to the affected Chat/Play/Plaza/Vibe entry pages, shared navigation/theme presentation and their scripts. Android changes cover navigation, wallpaper rendering, visible labels, coarse-location consent and timed Vibe playback; GuardianLab engine modules are unchanged.

- Final affected backend run: **117 tests passed**, including legacy listing compatibility, migrations, authorization, price/salary rules, discovery, concurrency, demo ledger, notifications and Vibe privacy.
- **36 JavaScript regression scripts passed**, including existing calls, chat, attachment/media, invitations, notification, scheduling, wallet and livestream checks, plus timed Vibes and swipe navigation.
- Android debug build and all 23 JVM tests pass. Packaged interface files match the tested server sources byte for byte.
- A wider earlier backend discovery run executed 319 tests: 306 passed and 13 errors came from legacy `test_rating.py` assumptions. Running that unchanged file against frozen version 31 reproduces the same 13 errors. Rating implementation/tests were not altered to conceal this pre-existing issue.
- Isolated browser QA used synthetic accounts only. Verified price-free skill publication and detail display, retained share prompt, conditional fields, unread counts, module destinations, selection colours, latest Vibe/timer, capture chooser, settings and left-aligned identity in both appearances. Plaza notification panel measured 360 pixels in a 720-pixel viewport. No live messages or adverts were created for these checks.

Physical camera recording, GPS acquisition and two-person privacy gestures require manual device verification; automated checks do not establish production readiness. Real deposits, custody, transfers and settlements remain disabled. Existing demo wallet/escrow presence is retained and explicitly simulated.

Deployment status and final commit are appended after installation and server verification.
