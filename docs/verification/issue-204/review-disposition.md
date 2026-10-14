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
  drift, changed protected-root locators, extra fields and unsupported actions must
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
approval and authority drift-during-getter cases. General observed getters that
raise are ambiguous; missing getters are unsupported. The item-inventory
reader conservatively marks raising/non-list inventory unsupported; that cannot
supply supported clip evidence. Observation/value budgets
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

## Independent delta GO and final test/document corrections

Independent Opus5.5/high delta review of
`724a829f6913eec7f939597c454c54aec5407058` completed exit0/is_error:false with
actual model `claude-opus-5-5`, unchanged head/consumed sources and verdict GO.
Result SHA-256 `7777cf850b1678ee59639cbea81d79153a27dd027a87c532cee794ad7b8a999f`.
B1/B2 were explicitly resolved. This is code-review GO only, not External
acceptance. The actual full fast pass at that revision includes 520 Python
tests in93.81s, 440 Vitest and61 Node tests with all other fast stages passing.

N1 identified that the earlier request-only overlap attacks stopped first at
binding mismatch, not at overlap itself. Added matching handcrafted authority/
request cases reaching repository, installed-plugin and prepared-release overlap
checks. These must retain no output inside protected roots and report safe
retention unavailable on Console. This is a test-only correction; production
source pins and the independently reviewed code are unchanged.

Remaining conservative limits N2–N5 are retained, not silently redesigned:
audio/video candidate parent chains are coupled and empty audio resolutions
remain ambiguous; malformed codec inventories and observation/value budgets can
truthfully stop a small disposable-target run; heavily indented results can
exceed the result re-read hash limit, leaving printed/published partial evidence
without a hashes file; item-inventory exceptions/non-lists remain unsupported.
Any actual runtime encounter needs a bounded fix, affected checks and delta
review before final full validation. Method enumeration never certifies output.

N6: the ordinary bootstrap refusal-retention containment helper changed to
device/inode ancestry; ordinary delivery orchestration and #177 capability
guards are unchanged. Do not describe all ordinary bootstrap bytes as untouched.
N8: the historical initial-plan no-command statement is clarified; track-enable
gap source lists name direct getters, while parent count/inventory remains in
the raw observations used to gate support. Alias cases may skip on platforms
without macOS aliases; actual local fast-r2 had zero skips. Runtime inventories
are duplicated but fail closed on drift. No production source change is added
for these conservative limits without actual runtime need.

Checked #109's exact accepted synthetic target result against its acceptance
hash `ec802ea507524cc821b0215f989d7b01dd235796700f9e7ee10fee009be86797`.
It proves its saved target names and real Studio21.1.1/10 run, but records no
project/timeline UIDs. Thus that known handoff cannot supply the four required
current target identifiers. No UID is inferred from it or from a failed #204
preflight. Coordinator/Producer must resolve the exact trusted identity handoff
before operator authority or installation/native execution is authorized.
