# #168 contract-design draft — shared RecognizerPort / AlignerPort

## Status and authorization gate

**Draft for Producer review — not approved.** Written 2026-10-10 from the
word-timing v2 study (branch `claude/word-timing-v2`). Approval of a later
revision of this note would authorize only the contract artefacts listed under
"What changes". Until then, #45 (STT) and Research #16 may prototype against
this draft on branches, but must not merge code that depends on it.

Inputs: D-P009 (two local ports, recognised text drives alignment, Producer
text evaluation-only), D-P007 as softened on 2026-10-10 ("local is better":
a local option is mandatory; a clearly superior cloud option may also be
offered), #168's acceptance list, RVC #16's normalized-artefact requirements,
and the measured profiles in `docs/investigations/word-timing-v2-results.md`.

## Pipeline shape the contract must express

```
source media
  └─ AudioPrep (optional, per stage)        e.g. DeepFilterNet; never mandatory
       ├─ RecognizerPort  → RecognitionArtifact   (text + coarse anchors)
       │    sources: local ASR (Parakeet, Resolve Studio), cloud ASR,
       │             caption text (YouTube auto/manual), Producer text (eval only)
       ├─ ScriptReconcile (STT only, optional)   names spelled from the prompter;
       │                                          `heard` kept as fidelity evidence
       └─ AlignerPort     → AlignmentArtifact    (acoustic word bounds)
             └─ AgreementCheck (optional)        second aligner flags disagreements
```

Each stage is switchable per product profile (Research has no script, so no
reconcile). The study's measured finding that cleanup can **hurt recognition on
noisy sources** is why AudioPrep binds to a stage, not to the whole pipeline:
a profile may recognise on raw audio and align on cleaned audio.

## What changes (proposed artefacts)

### 1. `recognition-artifact/v1`

- `schemaVersion`, `artifactId` (content-addressed), `createdAt`.
- `identity`: audio content hash + prep chain (each step's tool, version,
  parameter hash), recogniser kind (`asr-local` | `asr-cloud` | `caption` |
  `reference-text`), provider, model, model revision/hash, parameter hash,
  language (BCP-47), keyterm-list hash when keyterms were sent.
- `consent`: processing location (`local` | `cloud:<provider>`), the
  project policy id that authorised it. Cloud artefacts without a policy id
  are rejected at write time.
- `tokens[]`: `index`, `display` (as recognised), `kind`
  (`word` | `event` | `filler`), `anchorStartMs`, `anchorEndMs` (nullable
  integers, source-time), `anchorPrecision` (`word` | `word_start_with_derived_end`
  | `segment` | `cue` | `none`), optional provider `confidence` (opaque,
  never compared across providers).
- `segments[]` (optional): recogniser segment bounds when the provider gives
  them.

Caption sources fit as `kind: caption`. YouTube auto-captions give
`word_start_with_derived_end`; manual captions give `cue`.

### 2. `alignment-artifact/v1`

- `identity`: recognition artifact id (+ reconcile artifact id when used),
  audio hash + prep chain, aligner, model/dictionary revisions, parameter
  hash, segmentation (VAD model + parameters) hash.
- `normalization`: the many-to-many map from recognised `display` tokens to
  aligner units (`textnorm` rules: edge punctuation, hyphen/letter-digit
  splits, spelled numerals). Each aligner unit carries `tokenIndex` + `sub`.
  One display token may map to several units ("1998" → "nineteen ninety
  eight"); several display tokens never merge silently.
- `words[]`: `tokenIndex`, `sub`, `text`, `startMs`, `endMs` (nullable
  integers), `status` (`acoustic` | `interpolated` | `unaligned`), optional
  aligner-native score (labelled with the aligner; **not** a universal
  confidence).
- `agreement` (optional): partner aligner identity, tau, and per-boundary
  `accepted` | `needs-review`.

Rules carried from #168/RVC #16: unaligned words keep null bounds;
interpolation never authorises a cut; reruns append a new immutable artefact;
changing any identity field makes a new artefact.

### 3. Ports (language-neutral interface, per-app adapters)

- `RecognizerPort.recognise(audioRef, profile) → RecognitionArtifact | Refusal`
- `AlignerPort.align(audioRef, recognition, profile) → AlignmentArtifact | Refusal`
- `Refusal`: `code` (`capability-missing` | `runtime-missing` |
  `consent-missing` | `input-invalid` | `provider-failed` | `timeout`),
  human message, retryable flag. No silent fallback to another provider or
  to cloud; a missing local engine fails visibly.
- `capabilities()` declares languages, timing kinds produced, local/cloud,
  and hardware requirements, so the product checks a profile before running.

### 4. Profiles (data, not code)

Named, versioned profile files select stages, providers and parameters, e.g.
`stt-local-free` (Parakeet → reconcile → MFA + guides → agreement),
`stt-resolve-studio`, `stt-cloud`, `research-captions`,
`research-local`. Exact membership comes from the results report and is a
separate Producer decision.

### 5. Conformance suite (shared by both apps)

- Fixture audio + recognised text with known answers (built from the study's
  frozen keys where licensing allows; synthetic otherwise).
- Checks: identity/hash determinism, null-bound handling, normalization
  round-trip (every unit maps back to exactly one display token), refusal
  codes, append-only versioning, and a timing tolerance gate (median and p95
  per boundary class) per declared profile.
- A deterministic fake recogniser/aligner passes the suite and is what product
  tests use.

## Explicitly out of scope

Take segmentation and script-row pairing (#53/#45 consume these artefacts);
UI; storage engine; Apple Silicon packaging evidence (a readiness gate for
#45/RVC #16, not for this contract); multilingual profiles (each needs its own
licensed fixture).

## Open decisions for the Producer

1. Approve the two artefact schemas above (or request changes).
2. Approve AudioPrep binding per stage rather than per pipeline.
3. Approve caption text as a RecognizerPort source kind for Research.
4. Confirm that cloud artefacts require a stored per-project consent policy.

## Producer decisions (2026-10-10)

- Decision 2 — AudioPrep bound per stage: **approved**.
- Decision 3 — caption text as a RecognizerPort source for Research: **approved**
  (final default pending the unlisted-upload keyed test).
- Decision 4 — cloud artefacts require a stored per-project consent policy:
  **approved**.
- Decision 1 — exact schemas: still open. Next step is concrete JSON Schema
  files for review; #45 may prototype against them on a branch meanwhile.

## Draft schemas (decision 1, for review)

`docs/plans/issue-168/schemas/`:
`recognition-artifact-v1.schema.json`, `alignment-artifact-v1.schema.json`,
`port-refusal-v1.schema.json`, `script-reconciliation-v1.schema.json` (STT only; reconciliation is its own immutable record holding `heard` and `text` per unit, referenced by the alignment's `reconcileArtifactId`) (JSON Schema 2020-12, closed objects, integer
source milliseconds, sha256 content ids over canonical JSON).

Fit check (`scripts/word-timing-v2/to_artifacts.py`, run with the repo's
locked jsonschema): ElevenLabs → reconcile → MFA + Qwen agreement (A),
Parakeet → MFA (B) and YouTube captions → MFA (B) all validate; the
agreement block marks 54/912 ElevenLabs-A boundaries needs_review at τ 70 ms.
A cloud recognition artifact with no consent policy is rejected (decision 4).
Not yet in `/contracts` or the generated TS/Python types: that move happens
only after Producer approval of these exact files.
