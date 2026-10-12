# Claude initial review disposition

Actual reviewer: Claude CLI 2.1.296, `claude-opus-5-5`, session
`2980c80a-dc73-40a2-9d9f-832ebc85b35d`. Reviewed exact commit
`2d9709d93a5300fad881a4c66283e3d05c20ab4c`; result **NO-GO**, with two
blocking findings. Exit zero established review completion only. The full
response, prompt, command receipt and log hash are retained in this directory.

- B1: changed the joining-gap rule to require nonempty whitespace. This
  conservative profile refuses zero-width gaps at either outer boundary and
  inside the selected phrase. Two valid-input mirror regressions exercise the
  former partial-written-word edit; the v2 validator accepts each input before
  the omission refuses. All 27 transform checks pass on the fix candidate.
- B2: three well-ordered retained segments now reach the exactly-one-lift
  refusal. A short but well-formed programme bypasses only fake render
  authentication to reach decoded-extent refusal. A 24-bit re-encoding of the
  16-bit source, with distinct file bytes, reaches decoded-source-alias refusal.
  All structural refusal cases assert their expected reason.
- Suggestions 1/2: adjacent observation hashes must match exactly; rational
  rate parts require integer types. Malformed row text returns a refusal.
  The port documents `ProofBuildError` for rejected receipts, and the fake
  reviewer uses that explicit exception rather than an optimization-sensitive
  assertion. Added typed-adjacent, rate and malformed-text regressions.
- Suggestion 3: independently constructed full stereo renders use -6, -3.5
  and -2 dB routes. A matching positive checks quantization-sized residuals;
  changing the observed speech gain refuses at the complete-channel gate.
- Suggestion 4: generation pins include recursive TypeScript sources/generated
  types and the three executed frozen Python proof helpers. Added hash coverage
  for those previously omitted seams.
- Suggestion 5: retained the established authorization-port boundary. The
  immutable binding authenticates the exact prior-dependencies hash together
  with request, revised document identity, decision and evidence pins, service
  configuration and fresh row revision/text. This proof sibling does not invent
  an additional base-document field or weaken that trusted-port requirement.
- Suggestion 6: retained the accepted conservative whitespace/sentence-boundary
  profile, without adding a generic bracket/quote repair engine. Explicit
  omission authority is required and unsupported joins refuse. Whitespace
  joins, including line breaks, normalize to the established single space.
- Suggestion 7: attempt 2 was deliberately interrupted after the launch detected
  a competing gate and the dependent launch was mistakenly started anyway.
  The owned command was stopped; it never supplied acceptance. Both interrupted
  attempts remain non-passing history and must not be reused as a full gate.
- Suggestion 8: delta review receives the relevant accepted v2 schema definitions
  for anchor-owner completeness; no shared schema or generated type changes.

Cloud-scope condition: the base Normalizer constructor only stores tool names
and profile; it probes tools lazily through `tool_fingerprint`. The issue's fake
normalizer pre-seeds the fingerprint cache and overrides normalization, so its tests
invoke no media tool. Any substitution still requires accepted-main validator
exit zero on the exact delivered integration tree and the approved profile;
reviewer eligibility alone is insufficient. No real acoustic/provider/native
gate is claimed. Corrected source `590c7ed817acdb386d1023010d88f2f3c7a023b8`
passed 53 serial focused Python checks and the fast gate with 349 non-slow
Python tests plus all TypeScript/generated/lint/type checks. Its frozen audit
retains all 285 unchanged pins. Claude delta review at `858d08e` returned GO,
conditional on final acceptance, with both blockers closed and no substantive
finding remaining. Actual model `claude-opus-5-5`, session
`a4f17ffc-0f42-42da-80ae-6402d014c865`; response and receipt retained here.

Delta suggestions S1/S2 remain optional: exact byte-alias refusal is traced
before decoding, and the transform independently rejects any unsupported
written-word join even if local acoustic consistency can be measured. Neither
allows an unsafe accepted text edit. S3 public receipts/prompts/logs are derived
with machine-home/worktree redaction; original raw hashes and public hashes
are recorded in public-evidence-sanitization.json, and originals remain local.
S4 wording now correctly describes the pre-seeded lazy fingerprint cache.

The subsequent receipt/handoff-only commit changes no source, tests, config,
lockfile, generated type, fixture, golden or toolchain. New JSON/Markdown/gz
files in this directory are not read by the generator or tests; the audit reads
only the unchanged frozen-source-pins.json, and Python lint reads the unchanged
audit.py. Executable/check inputs match `590c7ed`; retained passing evidence is
reused, not described as a rerun.
