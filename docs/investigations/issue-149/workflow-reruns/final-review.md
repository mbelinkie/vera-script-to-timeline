# Task ID #149 — final document verification

This is a bounded read-only audit of the retained Phase 10 W1–W7 records. It
made no Resolve calls, did not stage or replay a native action, and did not
edit another agent’s result document. It checked the records after W5 was
published and after the retained neutral-Y media analysis became available.

## Decision-ready status

All seven W rows are independently reviewed and their evidence is classified
in the row records. W5’s public comments are recorded in
`results.md` and `verdict-review.md` (Issue #149 comment 5964921838; Issue #141
comment 5964921987). The final W2 record is posted on Issue #149 comment
5965021351 and Issue #141 comment 5965021531. The final summary is posted on Issue #149 comment
5965027605 and Issue #141 comment 5965027786. W2’s required on-state output gates, S-off OTIO export,
neutral-Y render/analysis and saved checkpoint are evidenced. The optional
neutral-X render was not part of the codex-rerun pass gate and remains
explicitly unrun. #149 and #141 remain open and producer acceptance remains a
separate authority. The final seven-row classification is exactly five
reproduced named gates (W1, W2, W4, W5 and W7) and two adverse outcomes (W3
and W6); adverse means the named expected behavior was not observed, not that
the overall investigation failed.

The retained W2 neutral analysis is
`out/issue149-workflow-reruns-20261002-kit-01/w2-neutral-y-analysis.json`,
SHA-256 `7999408950a094fc134e89f3df0e218db1acecffcfd00884132461b6e1b491bd`.
It verifies fixture hashes, matching stream layout, all 16 neutral-Y words,
the three baseline pilot levels, 399 source-1 frames with zero mismatches,
and analysis equality with the W3 baseline. It does not create a neutral-X
render; that optional case remains unrun and must not be presented as tested.
The final saved checkpoint is retained. A later read-only observation recorded
timecode and Out-mark drift relative to that checkpoint; the cause is unknown,
and this post-save observation is not converted into a Resolve capability
failure or retroactive state claim.

## Row and contradiction checks

- W1 records the three subtitle requests, terminal subtitle/render polls,
  deliberate cut geometry, and the checker limitation. Its checker failures
  are identified as shape mismatches rather than Resolve failures.
- W2 binds both on-state OTIO exports and render polls, operator restoration,
  the required S-off/neutral-Y export and render analysis, raw journals,
  snapshots and the saved checkpoint. The earlier X/Y poll-hash binding
  correction is present. The optional neutral-X render remains unrun. The
  final read-only guard and its drift-comparison hash are also bound; the
  failed phase-omission attempt is classified as a harness failure with no
  Resolve call.
- W3 is adverse on the current 21.1.1.10 Workflow Integration run: the
  mapping mute flag changed and read back, but A2 PCM and number words stayed
  at baseline. The Edit/reselected follow-up has the same result. This remains
  a context-specific contradiction with #149’s earlier Console result, while
  matching #141’s adverse mapping result. This is not a global Resolve
  capability claim; fixture, occurrence and integration context are preserved
  as possible differences.
- W4 scopes the timing result to the measured constant 37.5% case. Embedded
  linked A1 followed the V1 retime, while separately sourced linked A1 did not.
  The record does not generalize either behavior to all linked audio, 29.97
  fps or variable curves.
- W5 binds X-current, Y-current and X-queried-while-Y-current getter
  envelopes, with selection restored. It correctly treats the all-false
  inactive read as a context miss, not stored mute state or a global failure.
- W6 uses a same-layout replacement with an audio stream. Its expected decode
  failure was not reproduced; all four renders retained source ID 1, including
  after native relink returned `True`. The record reports this as an observed
  no-switch and keeps cache/context causes open.
- W7 is the named locked selected-delete/API-disable guard only. It preserves
  the four item identities/content and restores locks; it makes no atomic
  transaction claim and no universal setter-guard claim.

## Evidence and invariant checks

The seven row files are present and each has a Task ID, challenged claim,
classification, native/runtime identity, operation or precondition evidence,
measured result, raw evidence bindings, limitations or alternative explanation,
and VERA consequence. `results.md` and `final-summary.md` contain one row for
each W1 through W7, with W2 classified as reproduced for the required gates.
The checked W2–W7 dispatches retain one configuration, launch
receipt and result receipt per action; no duplicate action ID was found in the
retained action set. Referenced result hashes and the W2 neutral analysis hash
were recomputed from the local files.

The local Markdown link audit checked 23 relative links across the workflow
rerun records and README; all resolved. Public issue links are references to
the posted summaries. The raw Resolve journals, snapshots, renders and
fixture files remain local retained evidence and are not implied to be present
on GitHub.

The targeted W2 artifact check recomputed the neutral-Y analysis hash
`7999408950a094fc134e89f3df0e218db1acecffcfd00884132461b6e1b491bd`, the
corrected read-only observe result hash
`83e21501465419330e66e2305b8efb68acb32497ffac341c07f484ee8a00dfb3`, the
phase-omission harness result hash
`c3db0f50a8f95bc225be5801963addaca87278ffdf9d5ca315ffe55e93af44c4`, the
drift comparison hash
`08e0830898bd615839c321226c280eb215a476fde8eb560fded52956aa5e5459`, and the
SaveProject result hash
`c0673b83c946fbd200fa5c1bd76c325ac9bdc4f141a48faf08766f1fb7301aeb`.

## Material limits

The mapping-mute contradiction remains unresolved at the causal level. The
retime result is setup-sensitive. The W6 result does not establish a universal
relink failure, and W7 does not establish atomicity. Transcript evidence is
edited-mix subtitle output, not word-exact timing. Harness serialization,
page-context and other setup incidents remain classified as harness or
precondition evidence unless a native capability gate actually failed.

No further native action is required for this document audit. Publication of
the seven-row results and final summary is complete. The explicit optional
neutral-X gap and unknown post-save drift remain in the handoff. Producer
review remains pending and #149 must remain open.
