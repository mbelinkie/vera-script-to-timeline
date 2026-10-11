# #191 acceptance handoff

This is a local, pure and fake-service proof package. It does not qualify real
speech, native Resolve actions or provider execution. The exact Producer
authority is #189 at `094b1ca4d21dbaf063993ac33c7bb818d26941d5`, including
CN-189-A/B; see [the acceptance record](https://github.com/mbelinkie/vera-script-to-timeline/issues/189#issuecomment-6110965059).
Source/dependency hashes are retained alongside this handoff.

## Walkthrough

1. `verify_selected_omission_v2` receives canonical frozen document bytes and
   separately pinned observations/profile. Its required trusted callback
   authenticates review, native inventory, actual lift, render and listening
   receipts. It reviews exactly the selected contiguous interior tokens and
   immediate retained neighbors against the original source bytes. It requires
   one non-ripple split with preserved record/source coordinates and unchanged
   unrelated routes. Both full stereo programme renders are reconstructed with
   observed controls; per-channel RMS <= 0.0004 and every 20 ms RMS <= 0.006.
   Unknown, partial, aliased, malformed or stale evidence refuses. A successful
   report still says `local_consistency_only`.
2. `applyAcceptedOmissionV2` accepts an explicit current decision/evidence pin,
   validates v2 before and after, removes the selected text once and preserves
   surviving token IDs. Removed anchor endpoints refuse. Surviving range quotes
   refresh using exact affinities; unrelated rows, supporting items and source
   provenance survive. The result includes a complete revised-row request.
3. `prepare_replacement_row_v2` receives the actual existing NarrationService
   and an authenticated authorization. It freezes source, configuration, policy,
   cost, request and prior-dependency identity before calling the service. A
   cache-scoped intent prevents retrying an uncertain missing synthesis result
   through another output directory. Verified cached replay makes no extra call.
   Fresh row revision, text, audio, asset and provider timing pins are required.
4. `finalize_replacement_row_v2` rechecks the service cache and immutable receipt,
   authenticates fresh sparse boundary review against those exact bytes, and
   replaces only the changed narration dependency. It invokes the actual v2
   compiler twice and requires identical manifest/report bytes and unchanged
   inputs. It publishes immutable handoff/preview files only after verification.

The new siblings are proof-only internal modules, with no package export,
shared schema, generated type, frozen fixture or accepted-test change. The
Python/TypeScript bridge requires the established pinned Node v24.19.0. It
uses the compiler's canonical bytes rather than the narration cache serializer.

## Judgment calls and limits

- Known fixed gain, direct mono/stereo routing, zero pan and no effects/sends/
  automation form this bounded audio profile. Unsupported controls refuse.
- Full programme/source PCM is bounded to 3,000,000 samples per channel and
  16 sources, preserving the accepted conservative local proof scope.
- Identical prior/new provider timing hashes refuse, including identical empty
  payloads. Fresh acoustic review does not override that conservative criterion.
- Sparse review supplies only required fresh endpoints; naturally supplied
  provider marks are checked against new text/audio. No guessed ends or PCM
  splice is used.
- Narration integration tests are slow-marked for repeated external Node
  compiler calls and run serially in full validation. Synthetic audio remains
  in the fast gate.

## Validation evidence

Pending full validation and Claude review. Focused TypeScript: 25 transform checks passed, with focused
lint and workspace type checking. Focused Python: 22 audio checks and 19 narration checks
passed. Independent review found reused-timing and malformed-WAV refusal gaps;
both were fixed and independently rechecked. The review retained no unresolved
finding. The frozen audit verifies all 285 pinned files and no modification of
any pre-existing tracked file. Full acceptance must identify the committed
source revision, full log SHA256 and completion receipt before closure.
The producer's additional Claude CLI antagonist review must cover that exact
checked source revision, timing/acoustic bounds and refusal cases before closure.
Retain its response and disposition; substantive fixes require affected checks
and Claude re-review. A failed/unavailable CLI is an unmet gate.

`VITEST_MAX_WORKERS=1 npm run validate:fast` passed: generated types current,
TypeScript lint/types/tests, Python lint/types and 339 non-slow Python tests
with two workers. Elapsed 131.989 seconds; log SHA256
`88710355bce7e31bf332ed28e1659c7001e567c864c25041193de520d5277689`.

The inherited workspace lockfile lacks `packages/word-timing`. Clean `npm ci`
therefore fails before implementation validation; [Inbox #193](https://github.com/mbelinkie/vera-script-to-timeline/issues/193)
records the bounded repair. Validation uses the unchanged root lockfile's
recorded workspaces installed in a temporary staging directory, then copies
the resulting dependencies into this checkout. No manifest, dependency version
or lockfile was changed. `audit.py` verifies installed root dependency versions
against the unchanged manifest/lock and records runtime/lock/source hashes.

## Required later external gates (#145, #190, #178)

1. Independently review original selected/neighbor onset and end supports, and
   listen to source and edited mix; authenticate those exact artifacts.
2. Establish an actually frame-safe native audio lift without ripple or clipped
   neighbors, and retain authenticated intent/effect/completion evidence.
3. Obtain actual provider identity, consent, privacy/data-policy and cost
   authorization, then retain the actual whole-row provider/cache result.
4. Authenticate complete pristine, edited and rebuilt render settings, target,
   bytes and native source/route/control inventory; reject fake job IDs.
5. Review required sparse endpoints on new audio, qualify fresh media handles,
   native rebuild/save/reopen and final Producer judgment.

No producer repetition of deterministic checks is required for this Automated
issue. Closure does not authorize those external actions, merge, deployment or
the next issue.
