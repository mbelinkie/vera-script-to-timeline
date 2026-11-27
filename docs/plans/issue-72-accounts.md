# #72 accounts — Cloud implementation

## Pre-work check
1. Members gain access to the correct script with current Producer/Editor/Viewer permissions.
2. Authority: November 26 batch go-ahead and accepted r36 S07; Viewer comments, explicit discard after demotion, separate access-ended state.
3. Simplest version: opt-in trusted account-session adapter, account panel, strict access/membership endpoints over #379; local launch remains unchanged.
4. Large, bounded slice, targeted within one working day; no provider acquisition or collaboration/comments/history UI expansion.
5. Existing focused service/Chromium suites and required CI exercise identity isolation, current permission checks, revocation and saved attribution. User explicitly authorized Cloud tests.
6. Visible finish: protected complete PR, review, required CI; Producer acceptance retained separately.
7. No Resolve check applies; this slice's real application is Chromium and the service with disposable data.
8. CLI board mutation unavailable; connected GitHub tools recorded claim. No implementation blocker.

## Boundaries and ownership
#739/#740/#741 merged before slot acquisition; base f51a5e9b. #72 holds first serialized shared-shell slot.
Own account-panel.js/css, src/account-session.ts, authorization service/policy/tests and account-prefixed tests. Slot wiring: authoring.ts, serve.ts, app.js/index.html, documents/api.ts. Additional slot paths: host/src/index.ts (export account adapter port), documents/test/api.test.ts (r36 Viewer create/replay and editing-only resolution), documents/src/service.ts (optional transactional rename lease), documents/src/comments.ts and existing comment permission regression (r36 guard only), host/test/authoring.browser.test.ts (wait after reload). No other feature module, shared contract, manifest, lockfile or applied migration changes.

Persistence uses existing stable actors, membership, version/session revocation and immutable audits. List authorization and read occur in one transaction. Role changes reuse changeMembership. No names/emails, invites, project enumeration, identity architecture, local-agent or native changes.
Account mode requires a trusted host session adapter returning an independently verifiable suite bearer for the current session; credentials never reach browser JSON/storage. Every request re-authenticates and rechecks membership. Exact origin/Fetch Metadata/custom header plus session-bound CSRF protect browser requests. Account mode cannot fall back to the QA identity. Unconfigured provider fails closed. Synthetic adapter is test-only; LIVE_PROVIDER_UNVERIFIED.
Research is independently authorized and unavailable in account mode unless a future actor-specific adapter is supplied; never reuse local QA Research access. Build/revision attribution remains server-owned. No production deployment or Mac acceptance.

## Delivery evidence
Pending implementation and verification. Producer acceptance is not implied by code or merge.

## Review and evidence
- `npm run review -- /tmp/vera-72-review.md` attempted once: Claude CLI unavailable (`claude: command not found`). Claude review is deferred, not claimed completed.
- Independent Codex review found the missing browser write lease (held PUT could survive demotion/promotion between polls), incomplete sign-out draft protection, repeated access-ended focus, and a spurious Retry button. All addressed. Browser mutations now carry an existing #379 write lease; document/Extras/rename persistence checks it in the committing transaction. Promotion never renews it implicitly; explicit discard/reload opens a fresh lease.
- Real HTTP/PGlite and WebSocket tests prove actor separation, forged-session refusal, exact Origin/Fetch Metadata/CSRF, Viewer write refusal, stale leases, last-Producer protection, server-pushed demotion and removal closing 4403. Collaboration's existing Node client reports a role change in its roster; #73 must consume server role changes in its own UI.
- Chromium proves Producer add/change/remove access, keyboard focus, Viewer rendering, held command and held PUT revocation (including both role changes hidden between polls), explicit discard, promotion without replay, copied-link denial, reload after removal, signed-out and unconfigured-provider states. Covers 1280×800 and 1024×768.
- Guard mutations: roster authorization, last Producer, revoked write session, Origin and CSRF each made a focused synthetic test fail; every mutation restored. An initial Origin mutation was still denied by the inner authoring guard; adding an account-status Origin assertion exercises the outer boundary directly and detects its removal.
- Legacy Chromium suite: 138 passed, one pre-existing intentional skip, one reload timing assertion exposed by asynchronous account discovery; changed that assertion to poll the same expected cards, then its focused Chromium check passed. Required CI reruns the complete suite.
- Authorization suite 24 passed; document access/API 12 passed and comment service 12 passed; focused collaboration/WebSocket 17 passed; account/host check 47 passed before the additional unavailable-provider browser case. Final gate and exact-head CI results are retained on PR #751.

## Handoff / acceptance limits
Implementation PR: https://github.com/mbelinkie/vera-script-to-timeline/pull/751.
No production identity provider has been acquired or configured: LIVE_PROVIDER_UNVERIFIED. A trusted host must inject AccountMode/BrowserAccountPort; default local launch is unchanged. Account-mode Research is honestly unavailable pending an actor-specific independent adapter. No email invitations, project listing, collaboration/comment/history UI, native Mac/Resolve acceptance, live deployment or production data touched.
Producer acceptance remains pending: judge role/actions, demotion notice and explicit discard, access-ended wording/focus against accepted r36 S07. #692 already registers #72 and owns deployed-product verification; Cloud tests and CI do not establish deployed conformance. Keep #72 In review and Acceptance=Producer after technical delivery.


## CI follow-up
The first CI run caught a roster assertion before its asynchronous read completed; it now waits for the unchanged expected three members and native dialog focus. A later run exposed a queued prompter-close event stealing editor focus before a keystroke. A deterministic real-Chromium close-then-focus regression fails before the handler fix. Close handlers now preserve a newer user focus; normal native return focus remains intact. No permission assertion, required check or timeout was weakened.
