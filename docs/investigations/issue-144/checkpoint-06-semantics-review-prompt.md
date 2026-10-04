# Claude checkpoint 6 — visual semantics and prior native corrections

Continue independent review of VERA #144, repository reads only. Do not edit,
run tests, connect to Resolve, inspect private media/credentials, invoke
providers, publish, install tools/plugins or change claims. Producer authorized
direct CLI exchange and regular reviews of plans and finished segments.

Read the completed segment:

- `packages/contracts/src/issue-144-semantics.ts`
- `packages/contracts/test/issue-144-semantics.test.ts`
- `python/vera_timeline_agent/roundtrip_native.py` and `roundtrip_build.py`
  (checkpoint5 corrections)
- `docs/investigations/issue-144/checkpoint-05-disposition.md`
- `docs/investigations/issue-144/retained-uid-evidence.json`
- current full plan and the accepted compiler/validator as needed.

Prior concerns: native inspector no longer echoes authoring event fields. It
reads source path/hash, native track kind/index, record/source ranges, UIDs,
enabled/speed, then uniquely maps pristine package/path/geometry to a sidecar
authoring ID. No per-clip provenance write is claimed. Later UID checks retain
ancestry. Custom replay calls the unchanged #35 completed-artifact verifier
before fresh callbacks and uses canonical derived paths. Corrupted-path check
was red, then passes without invoking the inspector.

Your UID concern was scoped to #34's adapter, but #141 is also an accepted
starting boundary. Hash-verified retained capture contains project, timeline,
item and media-pool UIDs. Read `docs/investigations/issue-141/probe.py`'s
observe/item_evidence and report.md lines416–417 plus the retained UID JSON.
This establishes a historical named native observation, not new-target/current-
build qualification. Do not request an unauthorized accepted-source change.

New semantics: actual baseline compile must match; adjacent observations must
match; current script must equal baseline; complete item/source/native inventory
and links bind identity. Supported operations are the linked +25-frame move and
-25-frame end trim at25fps. Sources stay unchanged. Enumerate canonical
before-first/after-last intervals within one narration block (max64 tokens for
this proof), compile each candidate through unchanged compileTimeline, and
require one unique pair of reproduced video/audio ranges. Check video/shared
audio clearance and validator-passing coverage. Ambiguous rounded boundaries,
picture-only changes, wrong source/UID, unavailable media and stale reads refuse.

Explicit accept/reject choices bind the full report hash and every proposal ID.
Apply supported ranges only, preserving narration text/token order/version;
bump visual/anchor versions, local sequence once, empty local state vector and
canonical document hash excluding itself. New deterministic UUIDv5 build/
manifest/report IDs; actual composed compile must reproduce accepted geometry.
Identical pure replay is identical; all-reject yields no revision. No file writes,
native effect, baseline promotion or spoken-omission implementation is implied.

Checks: missing module red; initial fresh-ID formatting error caught and fixed;
20 new semantic cases +62 accepted compiler/validator cases =82 passed.
Focused ESLint/typecheck and diff check pass. Prior native/prepared corrections
27 passed, Ruff/mypy pass. Full validate is being recorded separately on the
review commit. Static review is not independent test execution or acceptance.

Review concrete bugs: alias/identity bypasses; parser/type assumptions; candidate
uniqueness/precision; exact source and record endpoints; clearance/coverage;
accept/reject completeness; stale/malformed decisions; canonical revision hash/
version/new-ID rules; composition of multiple accepted edits and replay. State
whether this segment can be connected to the host proof workflow.

Next planned seam for review: one issue-owned stdout-only TypeScript entry
(propose/decide) wraps these pure functions and the actual canonical serializer,
with scoped Node source-resolution hooks, pinned runtime, input/source hashes
and separate refusal/fault exits. The Python file-driven host strictly parses
literal operator inputs, serializes operations under a local advisory lock,
publishes proposals/decision/revision receipts immutably and retains old inputs.
Before decision application/rebuild/promotion it requires a fresh guarded WI
capture request/response, tied to a unique nonce, target UIDs and input/code
hashes; two equal captures detect observed drift only. A cached file is not
freshness authorization. Missing native response waits visibly. Actual builds
reuse the completed PreparedBuild/NativeStages seams; revision inputs get fresh
IDs and no automatic baseline promotion before fresh verification.

The stdlib WI entry will check required getter callables/results through #141's
supported object boundary and uniquely map pristine observed facts. Only a
separately authorized disposable #145 request may link/render/create targets;
#144 tests inject fakes and execute no native actions. Unknown controls/effects/
routing cannot qualify a spoken-omission positive. Producer narration route/
wording remains pending. Qualified W1 omission and new recording splice are
separate unfinished segments, not a visual mapper claim.

Return actionable severity/location/failure example/smallest fix. Distinguish
current bugs from unimplemented seams and qualification required in #145.
