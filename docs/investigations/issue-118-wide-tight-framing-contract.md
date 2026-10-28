# Single-camera Wide/Tight framing contract — #118

Status: working contract record. DeepSeek-V4-Pro's bounded source analysis is
in progress; Codex owns verification and integration. This record does not
complete #118 or authorize a production implementation.

## Authority and scope

- [#118](https://github.com/mbelinkie/vera-script-to-timeline/issues/118)
  owns this document-only technical contract.
- [#117 acceptance](https://github.com/mbelinkie/vera-script-to-timeline/issues/117#issuecomment-5629523489)
  remains authoritative. [PR #346](https://github.com/mbelinkie/vera-script-to-timeline/pull/346)
  delivered its accepted records and section-14 wording to main at
  `34d432d37b20c8332cf263951536b0d5db263d5d`; no new design acceptance is needed.
- The accepted [#55 presenter-still contract](https://github.com/mbelinkie/vera-script-to-timeline/blob/a561735e7b0c735ccd6185aa407e82581a19b2d9/docs/investigations/issue-55-presenter-visual-contract.md)
  and [#56 ordered-visual contract](https://github.com/mbelinkie/vera-script-to-timeline/blob/9e2b8817ffe97fbc9d6fcf31099aca578c5022bb/docs/investigations/issue-56-ordered-visual-contract.md)
  are immutable inputs; this successor must identify its narrow amendments.
- Current [verification policy](../VERIFICATION_POLICY.md) supersedes old
  review, approval and full-local-suite instructions in those historical records.

Exactly `wide` and `tight` describe treatments of one camera. Every ordinary
On Camera appearance and every return to an On Camera parent needs its own
explicit value. A return to another visual forbids presenter framing. Framing
does not choose host visibility, restart picture source time or cut dialogue.

This issue edits no schemas, generated types, fixtures, compiler or adapter.
It performs no Resolve project mutation, production-media operation, creative
grade, multicamera work or Claude Design work.

## Verified starting point and capability limits

| Surface | Current evidence | Limit for this contract |
| --- | --- | --- |
| Authoring | `PrimaryVisualPayload.on_camera` stores `presenterChoiceId`; `ReturnSlot` stores parent and boundary | Neither stores a framing key today; adding a key cannot be described as shipped behavior |
| Temporary presenter | The v2 compiler emits a configured/fallback still with contain, center, black canvas and no motion | #55's base composition must be explicitly reconciled with the #117 two-treatment preview |
| Recorded presenter | The v2 compiler reports a blocking review diagnostic even when alignment exists | A valid alignment alone does not provide a qualified recorded-picture route |
| Native transform | The installed still-composition path writes and reads neutral `Pan=0`, `Tilt=0`, `ZoomX=1`, `ZoomY=1` with dynamic zoom disabled | This does not establish non-neutral units, raster mapping or Wide/Tight transforms on continuous footage |
| Rendered continuity | RK-19/#250 measures an advancing root through a transparent 320×720 presenter still, an independent overlay and the continuing root on return | Transparent-still composition is not proof of continuous presenter reframing |

Source pointers at this document's starting main:

- [Authoring contract](../../contracts/script-document-v2.schema.json),
  `PrimaryVisualPayload` and `ReturnSlot`.
- [Compiler](../../packages/contracts/src/compiler-core-v2.ts), recorded
  presenter refusal and temporary-still generation.
- [Native adapter](../../python/vera_timeline_agent/workflow_v2.py),
  `_still_composition_properties` and still-composition readback.
- [Resolve knowledge RK-19](../RESOLVE_KNOWLEDGE_GUIDE.md#rk-19--transparent-presenter-proof-is-not-continuous-presenter-reframing)
  and [#250 report](../verification/issue-250/PRESENTER_QUALIFICATION.md).

No new native check is authorized by this record. #312 retains the sole
Resolve/CPU window. Unproved non-neutral calibration and continuous-footage
behavior must remain explicit capability gates for the #47/#119 handoff.

## Analysis provenance

The bounded DeepSeek request contains only sanitized public GitHub/source
excerpts. It has no tools, private media, local paths, runtime payloads or
credentials. Its output is a draft to verify, not external-application evidence.
Connection, billing and cumulative usage records remain private.
