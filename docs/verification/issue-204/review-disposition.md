# #204 initial NO-GO disposition

Independent Claude Opus5.5/high reviewed candidate
`560a44ed6e72a3c82f86e812fd9bde3ff386ec09` with tools disabled, safe mode,
strict MCP configuration and session persistence disabled. CLI2.1.299 completed
exit0, `is_error:false`, actual model usage `claude-opus-5-5`, verdict **NO-GO**.
Raw result SHA-256:
`c185673f94395fb3910709cbd6151455d5b32a23d9d0c2de4bec619297a934c9`.
Full review, invocation/source/context pins and actual receipts are retained
beside this disposition. Exit0 never supplied review GO.

## Blocking fixes

- B1: clip-level supported visibility now requires the actual audio track-count
  observation and every audio-item inventory row to be complete/supported;
  those parent rows are included in each gap's source list. Missing/overflow
  inventory refuses a complete-control claim. Render resolutions/codecs require
  complete parent format/codec observations. Added partial/missing/overflow and
  incomplete-parent tests rather than weakening support assertions.
- B2: installed subprocess tests now execute the qualification branch, checking
  exact pre-import request/authority/source/target provenance, read-only started
  files and later no-injected-object refusal. Authority byte/binding/approval
  drift, protected-root overlap, extra fields and unsupported actions must
  retain a bootstrap refusal before imports/controller attempts. Explicit CLI
  authorize/request tests cover separate operator procedure and missing flags.

The first red run reproduced **8 failed/26 passed in9.71s**. Initial fixes
passed **34 tests in3.88s**; subsequent integrity tests and unchanged v2 handoff/
delivery regressions passed **95 in11.17s** before four final additional cases.
Those are intermediate development results; later retained affected/fast/review
receipts identify the final candidate. Original failing logs are preserved.

## Additional applicable integrity fixes

Path containment checks compare existing ancestor device/inode identities,
including releaseRoot, so case-insensitive APFS/firmlink aliases cannot place
evidence inside protected inputs. Hardlinked inputs refuse. New macOS alias
cases and hardlink tests cover the convention without editing accepted tests.
Bootstrap provenance reads bind regular single-link descriptor identity/extent
and before/after metadata. Its independent safe authority output is used for
refusal retention when a tampered request chooses a protected directory.

Observations retain the last successfully checked source/input/current-target
guard boundary. Later raw reads are kept with `contextVerified:false` and
ambiguous status rather than feeding supported classifications. Added source,
approval and authority drift-during-getter cases. Existing getters that raise
are ambiguous; missing getters are unsupported. Observation/value budgets
retain partial reports rather than dropping all evidence, and Console printing
precedes final result publication. Bootstrap-started records become read-only.

Actual SDK Audio Mapping docs specify `track_mapping` as an object keyed by
track number. The parser now checks that documented shape, channel indices,
mute boolean and type string; no channel routing is inferred. Format tokens
remain opaque bounded strings used only as documented getter arguments.
Malformed neighbors are ambiguous while remaining audio/queue observations
continue; no speculative identifier regex silently stops all later getters.
New oversized-getter and opaque/malformed-format tests cover these refusals.

Strict authority/issue/confirmation cases reject unsupported scalar types;
approval timestamps require timezone. Test traps record every non-getter attempt
before raising, so stopped-path tests cannot silently swallow a mutation.
Issuer metadata remains explicitly self-declared local provenance; independence
is procedural, following the separately invoked operator command, not a signature
or a hash's claim to authenticate its own issuer. No new authority is issued by
the agent, and no real target UID is guessed.

## Ordering and held gates

Producer asked whether actual-app evidence should precede full validation.
Coordinator confirmed the final sequence: bounded review fixes and affected
checks/fast/independent re-review, then exact approved operator/UID/install/runtime
gate and actual injected read-only report, then any runtime fixes/delta review,
and **final full validation on the final delivered state**. The question grants
no blanket installation/native authority. No full gate or real-app action has
run; #204 remains open. Trusted target UID handoff, operator-issued authority,
None confirmation, actual report and unchanged-target evidence remain explicit.

Frozen contracts, fixtures, goldens/generated output, accepted tests, ordinary
#177 guards and #190/#192 native/records source are untouched. No qualify_build,
render, setter, creation, save, export, provider or UI/external scripting route
was added. Independent delta review remains required; these fixes alone are
not a final review verdict or External acceptance.
