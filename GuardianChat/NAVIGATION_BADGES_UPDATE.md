# Navigation badges — version 33

The existing bottom Chat, Calls and Vibe icons now use separate account-scoped counters in both Android and browser interfaces. Existing layouts, icons, destinations and Plaza/Play notification categories are preserved.

- Chat totals unread incoming messages across conversations; call events are excluded. Reading one conversation only reduces that conversation's contribution.
- Calls counts incoming missed/unanswered-cancelled audio and video calls. Outgoing, answered, declined and ongoing calls do not count. Successfully displaying call history acknowledges only the missed-call IDs actually rendered, while a hidden/background page does not. A newer missed call outside that snapshot stays unseen. History remains available.
- Vibe counts individual, active, permitted, unviewed posts across Public and Private Vibes. Own posts, expired/deleted media, muted authors, blocked accounts and inaccessible private audiences do not count. Merely opening the list does not clear views; the existing display-before-view receipt clears each post individually. Privacy revocation and expiry remove unavailable items from the count.

The existing authenticated `/navigation/state` response adds `missed_calls` and `unseen_vibes`. New authenticated `POST /navigation/calls-seen` accepts up to 200 displayed call IDs, validates ownership, and records them atomically and idempotently. The repeatable migration adds only `navigation_call_views(uid, call_id)`. No existing data or call/message/Vibe records are deleted or renamed. Calls and message reads cannot clear Vibe views, or vice versa.

Counters use the existing red/pink top-right badge style, hide at zero, and display 99+ for large counts while exposing the full number to accessibility. Foreground refresh remains two seconds on Android and three seconds in the browser, with immediate refresh after browser acknowledgement/view. Network failures retain the last known badge.

## Verification

- Final combined backend navigation, core chat/call, Vibe and privacy run: **87 passed**, including restart persistence, atomic authorization, new-call snapshot races, partial message reads and view-only Vibe clearing.
- All 36 JavaScript regression scripts passed, including displayed-call acknowledgement, hidden-page protection, separate counters, clearing and account logout.
- Android debug build and 23 JVM tests passed. Version code 33, version name `0.33-navigation-badges`; the application ID is unchanged.
- Isolated browser QA with synthetic accounts showed Chat 3, Calls 2 and Vibe 2 simultaneously. Opening call history cleared Calls while Chat and Vibe stayed unchanged. Opening one Vibe moved that author under Viewed and reduced Vibe to 1; simply opening the list left it at 2.
- Original X-Orbit repository, artwork and GuardianLab engine are outside this change. The previously documented legacy rating-test errors remain outside this scope.

## Deployment

Deployed 26 October 2026 from implementation commit `9c7e1a386b1ec22928b5e2f806b674901f67e163`. Both `https://localhost:8766/` and `https://localhost:8768/` serve the frozen tested source. Database integrity and retained user/contact/message counts were verified after the additive migration. Version 33 is installed on the S21; authenticated API checks confirm @s21 and its saved server remain intact. The browser retained Mainfirst and visibly showed Chat 1 and Vibe 2; Calls correctly had no badge at zero. No live messages were sent or calls generated for this verification. Physical phone badge interactions remain a manual verification item. Version 32 was superseded before deployment.
