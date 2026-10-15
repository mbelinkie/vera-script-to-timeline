# #167 delivered-design review dispositions

Initial candidate: `2e4da712d220cfe03c3cdfc9e777712cdf8619f1`.
Required independent Claude CLI review returned **NO-GO**, exit 0, three
blockers; [exact result](claude-initial-review.md), [prompt](claude-review-prompt.md)
and [input identities](review-inputs.json). Full submitted read-only bundle is
retained privately at `out/issue167-review/input.txt`; no native/private content
was included. The CLI had no tools or MCP servers and could not mutate anything.
The intake GO was not used as design-review acceptance.

Fix candidate: `f326facbdf57fca60cf54de976d98612cecc17e6`.
[Delta prompt](claude-delta-prompt.md), [exact input identities](delta-inputs.json);
submitted bundle at `out/issue167-review/delta-input.txt`. A fresh authoritative
live #167 body was included, independently confirming the claim/status/criteria.

| Finding | Disposition |
| --- | --- |
| B1 adapter outcomes contradicted design | Fixed: compiler planned/blocked/unqualified/manual; adapter can report verified/failed/blocked/unqualified with actual stage/zero-write/partial-write receipt. No compiler verified claim |
| B2 undefined hashed endpoint evidence | Fixed: one closed versioned record, exact accepted v1/v2 hash-field mappings and full input hash; explicit causal null rules and deterministic next-start tie selection; addressed boundary/cause inventory; verifier recomputes hashes and intervals |
| B3 missing v1 anchor definition | Fixed: named closed v1 anchor/timing types copying only v2 word-onset/audible-end shapes, exact UUID/text/version constraints and single-block owner. Current v1 has onsets only; audible-end requests visibly block without invented timing support |
| Optional v2 contentPin shape | Fixed: explicit discriminated v1/v2 closed variants |
| Optional recordRange wording | Fixed: addressed schedule always start/end; separate accepted v1 event remains start/duration with equality check |
| Optional v2 ownership | Explicitly deferred/unowned; all v2 deltas outside CN-167-P1 approval and #220. No v2 support promised; adoption requires a bounded steward-owned follow-up and separate materializer/contract approval; current closed-schema rejection remains |
| Optional binding hash/profile fields | Fixed: prefixed hash domains, trusted #99 profile issuer and exact receipt-byte domain; independent authority verification required |
| Optional Table classification | Fixed: new Table branch requires explicit provenance; lower-third legacy omission is not inherited |
| Optional diagnostic sort | Fixed: absent-first, code-unit string and numeric interval ordering |
| Handoff progress label | Audit explicitly records its pre-review snapshot; the plan states the future In review handoff rule, not a contradictory live status |

The required delta result and final checks are retained separately. Neither
Claude GO nor design acceptance approves CN-167-P1, runtime or a broader profile.

First delta review returned **NO-GO**, exit 0, on
`f326facbdf57fca60cf54de976d98612cecc17e6`; [exact result](claude-delta-review.md).
B1 was verified fixed; B2/B3 each needed one more explicit rule, and report hash
nullness needed a stage table. Fix candidate:
`824923d14271a5dd341b0df7c6cc1f5c47014dfb`.

| Residual finding | Disposition |
| --- | --- |
| R1 evidence identity/hash nullness | All block/version/timing/audio/text/input fields explicitly non-null for every basis; missing/failed/ambiguous owner dependency refuses. Boundary record now has schemaVersion |
| R2 token ID to v1 mark | Exact frozen token UUID lookup, quoted text and UTF-16 offset/value match to exactly one word mark; reduced timeMs/1000. Repeated labels cannot select a different token; stale/zero/multiple matches refuse. Accepted #7 schema extracts supplied to final review |
| R3 outcome hash inventory | Compiler planned success derives both schedule and plan; valid unsupported/manual semantics retains only schedule; compiler-blocked has neither; adapter replacements retain both compiler hashes and stage-specific receipt. Package independently rederives plan |
| Generated wording / v1 branch | Removed misleading v1/v2 generator wording; v1 schema includes only visual_event/v1_curated branches. Writers omit empty top-level cue array |
| Timing input locator / retained bytes | New cue-specific timingInputHash omits exactly audio.locator, retaining all other frozen dependency fields. Existing build/hash material is unchanged; exact timing record and narration audio bytes are retained/verified separately |

Final narrow delta [prompt](claude-final-delta-prompt.md) and
[input identities](final-delta-inputs.json) retained; submitted exact bundle at
`out/issue167-review/final-delta-input.txt`. It reviews these bounded fixes and
their related seams, reusing the earlier unchanged timing/profile review.

Final required delta review returned **GO**, exit 0, on
`824923d14271a5dd341b0df7c6cc1f5c47014dfb`; [exact result](claude-final-delta-review.md).
R1/R2/R3 are verified fixed with no blocking related regression. No further
product/design edits follow this GO. Remaining comments are non-blocking:
the accepted #7 UTF-16/token-version/hash verification rules remain binding;
unverifiable timing artifact bytes fail closed; stale/missing cue timing already
uses TIMING_UNQUALIFIED in design §6. Minor prose suggestions do not change
the contract. Native behavior and v2 support remain unqualified as stated.

All three Claude runs used `--safe-mode --tools "" --strict-mcp-config
--mcp-config '{"mcpServers":{}}' --no-session-persistence --output-format text
-p`, reading the retained bundle on stdin, with stdout/stderr and exit status
under `out/issue167-review/`. Existing unrelated local permission-rule warnings
appeared on stderr; all runs completed exit 0 with usable verdicts. No tool
access or write permission was granted to the reviewer. No waiver was used.
