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
Own account-panel.js/css, src/account-session.ts, authorization service/policy/tests and account-prefixed tests. Slot wiring: authoring.ts, serve.ts, app.js/index.html, documents/api.ts. No other feature module, shared contract, manifest, lockfile or applied migration changes.

Persistence uses existing stable actors, membership, version/session revocation and immutable audits. List authorization and read occur in one transaction. Role changes reuse changeMembership. No names/emails, invites, project enumeration, identity architecture, local-agent or native changes.
Account mode requires a trusted host session adapter returning an independently verifiable suite bearer for the current session; credentials never reach browser JSON/storage. Every request re-authenticates and rechecks membership. Exact origin/Fetch Metadata/custom header plus session-bound CSRF protect browser requests. Account mode cannot fall back to the QA identity. Unconfigured provider fails closed. Synthetic adapter is test-only; LIVE_PROVIDER_UNVERIFIED.
Research is independently authorized and unavailable in account mode unless a future actor-specific adapter is supplied; never reuse local QA Research access. Build/revision attribution remains server-owned. No production deployment or Mac acceptance.

## Delivery evidence
Pending implementation and verification. Producer acceptance is not implied by code or merge.
