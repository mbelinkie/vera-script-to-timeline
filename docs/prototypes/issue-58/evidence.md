# Issue 58 retained evidence — S04–S06 prototype

## Artifact and boundary

- Claude Design project: `VERA design feedback`
- Artifact: `Script to Timeline - Prompter Runtime and Suite Navigation S04-S06.dc.html`
- Review URL: <https://claude.ai/design/p/011eee38-8b6b-48aa-a154-d6c0060d4f23?file=Script+to+Timeline+-+Prompter+Runtime+and+Suite+Navigation+S04-S06.dc.html>
- Exact submitted prompt: `docs/prototypes/issue-58/claude-s04-s06-prompt.md`
- Exact S04 correction prompt:
  `docs/prototypes/issue-58/claude-s04-producer-correction-1.md`
- Visual baseline: the Producer-accepted `Script to Timeline - Two-Column
  Authoring S01-S03 v2.dc.html`; the prompt required a new artifact and did not
  authorize changes to that accepted artifact.

The artifact labels itself as a design simulation. It does not implement or
claim production export, synchronization, authentication, local-agent, media,
background-job, Resolve, or cross-product behavior. After Producer correction
1, the S04 action is named `Create prompter export`, and its result says
`Simulated — no file written`.

No contracts, fixtures, golden files, generated types, or shared tokens changed.

## Independent review observations

Review was performed against the rendered artifact on 2026-09-09. The checks
below record only results actually observed; they are not production-behavior
evidence and do not constitute Producer acceptance.

### Initial S04 observations before Producer correction 1

- Base output preserved F03, the intact F04 paragraph, and F10 in document
  order. It began `(OC)`, changed to `(VO)` and back to `(OC)` only at the
  represented host-visibility boundaries, and showed PAUSE and pronunciation
  as separately styled and accessibly named non-spoken cues.
- F05 Direction, F06 Citation, F28's zero-duration production marker, F32's
  excluded note, and the fictional source transcript were present in the input
  boundary but absent from prompter output.
- With annotations off and section labels on, PAUSE and pronunciation
  disappeared, section labels appeared, and all five observed spoken fragments
  remained unchanged.
- Repeating Revision A with the same options returned identical identities:
  text `sim-text-fe1cca` and sidecar `sim-cues-5c8f1c`, with equal content.
- `Missing camera state` removed the successful preview action, showed a
  non-color blocking notice, named `“as the tide turns and”`, offered `Go to the
  affected phrase`, and did not invent OC or VO.
- `Marker target removed` showed F28 as `UNPLACED · 0S`, retained the marker,
  kept it out of prompter output, and offered `Reattach` and `Dismiss`.

### S04 — Producer correction 1

- Claude edited the existing `Script to Timeline - Prompter Runtime and Suite
  Navigation S04-S06.dc.html` artifact in place from the exact retained
  correction prompt. The rendered S04 no longer contains the visible `Input
  boundary — Revision A` panel or an excluded-source inventory.
- The default base view is a compact single-column flow at both internal
  `1280 × 800` and `1024 × 768`: title and explanation, three checkbox options,
  document-sized prompter text, and the simulated creation action/result.
  Visual inspection found no horizontal overflow or independently scrolling
  content column.
- All observed non-spoken items use literal square brackets while retaining
  accessible pill semantics: `[OC]`, `[VO]`, `[PAUSE]`,
  `[SAY: Lunara = loo-NAH-rah]`, and optional `[SECTION: …]` labels.
- `Simplify brief mid-sentence camera changes` is checked by default. With it
  on, all five words in `as the tide turns and` remain and F04 reads
  continuously under OC. Turning it off restores a `[VO]` marker before that
  phrase and `[OC]` before `the reading begins to drift.`
- Repeating the unsimplified Revision A creation without changing settings
  left the identities unchanged: text `sim-text-38b59b`, sidecar
  `sim-cues-bed7e4`. Restoring simplification changed both identities to text
  `sim-text-39b59d` and sidecar `sim-cues-0293ba`.
- Creation displayed `Simulated — no file written`, frozen Revision A,
  simulated Download/Copy controls, and a secondary `Technical details`
  disclosure. The visible explanation says the text is for a teleprompter and
  the companion data supports matching recorded takes later.
- `Missing camera state` still blocked creation, named `“as the tide turns
  and”`, offered a return to the phrase, and did not invent OC/VO. `Marker
  target removed` retained the zero-duration marker outside prompter text and
  offered `Reattach` and `Dismiss`.
- Switching to S05 and S06 after the correction showed their prior headings,
  scenario matrices, and base content unchanged. The accepted S01–S03 artifact
  was not targeted by the correction.

### S05 — capability and revision boundaries

- Browser writing remained visibly available in all seven runtime scenarios:
  no agent, disconnected agent, connected Free, connected supported Studio,
  Resolve closed, external scripting off, and version mismatch.
- No-agent and disconnected states offered no executable local action. Resolve
  closed, scripting off, and version mismatch omitted `Build in Resolve` and
  gave scenario-specific remediation without a UI-automation fallback.
- The Free branch offered `Prepare Resolve timeline`, described a verified
  Resolve Import Package ending at `ready_to_import`, and named the manual
  `File > Import > Timeline` step. It did not claim Free UI automation or
  automated in-Resolve verification.
- The supported Studio branch described a running supported standard desktop
  Studio installation with external scripting enabled; outcomes were explicitly
  labeled simulated.
- Revision flow was observed as `Local changes · Revision B` → `Syncing ·
  Revision B` → `Synced · Revision B`. Preview was absent while unacknowledged,
  then produced `Simulated Preview B` with frozen source Revision B.
- After advancing the live head to Revision C, the preview remained frozen on B
  and showed `Newer live revision available`; retry copy said it would re-run
  the frozen source rather than follow the live head.
- The durable simulation retained job `sim-job-25d7b7`, source `Revision B ·
  frozen`, and stage `Verifying import package` across the artifact's simulated
  browser close/reopen. The unrequested Resolve-placement stage was labeled
  `Skipped — not requested`.

### S06 — navigation surface present

- The mode exposed all required destination scenarios: one destination, several
  destinations, no linked destination, unauthorized, stale, archived, unlinked,
  and destination unavailable.
- The rendered surface kept a round `VERA suite` product switcher distinct from
  the rectangular same-product `Project` switcher. The product menu contained
  exactly Research Video Clips and Script to Timeline; Research disclosed
  `Opens in a new tab`, while the source context remained visible.
- A reciprocal-direction control and `View safe handoff details` disclosure were
  present. The base explanation stated that Research and Script membership are
  independent and each destination rechecks its own membership.

## Responsive and accessibility evidence

- The artifact's 1280 × 800 harness rendered a 1280 × 800 container (1278px
  client width inside its border) with zero detected horizontal-overflow
  elements. Its visible controls used tab, radio, checkbox/button state, status,
  and alert semantics; every inspected status included text or shape in addition
  to color.
- The artifact includes a true 1024 × 768 reflow control rather than a
  scale-to-fit control. Required compact-width pointer/keyboard traversal,
  Escape/focus-return, long-name overflow, and the full S06 fallback matrix are
  intentionally retained as hands-on Producer checks below.

## Review interruption and remaining Producer judgment

The independent browser session stopped responding while the final S06 and
1024 × 768 interaction pass was underway. No correction prompt was sent and no
artifact change was made after the verified S04/S05 observations. Consequently,
this evidence does not claim that the remaining compact-width, keyboard, or S06
interactions were independently completed. They remain explicit acceptance
steps rather than being silently marked as passing.

Producer should use the ten-step checklist in
`docs/plans/issue-58-s04-s06-prototype.md`, with particular attention to steps
7–9. Acceptance requires an explicit reply:

`Accept #58 S04–S06 prototype states`

or the first correction in this form:

`Correction: <S04|S05|S06> — <first misrepresented state and intended meaning>`

Issue #58 may be placed in `In review` with this retained evidence. It must not
be closed or moved to `Done` without that explicit Producer acceptance.
