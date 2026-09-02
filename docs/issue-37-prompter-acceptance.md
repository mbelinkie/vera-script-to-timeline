# Issue 37 automated acceptance evidence — 2026-09-02

Implementation is complete for review on `codex/issue-37-prompter-export`,
based on `cf53ceba957af21f026b8c2bca1a8eee0be842f3`. No merge, closure, or next
issue dispatch is performed by this task. The Project authority is `Automated`.
The Producer-approved contract and subsequent mixed-sentence clarification
are retained in the [contract note](plans/issue-37-prompter-contract-change-note.md).

## Result

The library/CLI emits active narration with initial/change OC/VO markers and
opted-in non-spoken cues, plus the canonical typed performance-beat sidecar.
A sentence with partial VO remains one OC recording beat while the text keeps
the exact editorial VO transition. Explicit beat IDs survive export; legacy
sentence IDs are deterministic. Absent optional arrays require no migration
and never cause an input rewrite. No UI, provider, real script or media,
Resolve, transcription, or unrelated contract work is included.

## Retained checks

- Two consecutive final full gates exited **0**. Each passed generated-contract
  currentness, TS lint/typecheck, **141 contract tests**, **1 tooling test**,
  **6 progress tests**, **23 roadmap tests**, Ruff, strict mypy over **53
  files**, and **175 Python tests**.
- Full unabridged command/output/exit evidence:
  [run 1](verification/issue-37/validate-1.txt),
  [run 2](verification/issue-37/validate-2.txt).
- The real CLI ran twice per fictional input (four successful processes).
  For each input, `rtk cmp` proved text and sidecar byte-identical between
  runs and equal to their checked-in goldens. Independent SHA-256 checks
  verified the sidecar's text hash against actual artifact bytes.
- Removing the final camera-state range from a temporary acceptance copy
  returned exit **1** with `HOST_VISIBILITY_GAP` and
  `ANNOTATION_HOST_VISIBILITY_INVALID`. Neither requested artifact existed.
- A baseline audit of **53 frozen paths**, including every previously accepted
  test/fixture/golden, the other schemas/generated Python models, and both
  lockfiles, found no changes. `rtk git diff --check` passed.
- Machine-readable [commands, outputs, versions, hashes, and frozen-path list](verification/issue-37/evidence.json)
  preserve all CLI, byte-comparison, negative, and boundary results.

Toolchain: Node **24.19.0**, npm **11.17.0**, uv **0.12.5**, Python **3.12.14**,
Vitest **4.1.11**, pytest **9.1.1**, Ruff **0.16.4**, mypy **2.3.1**, and
datamodel-codegen **0.75.1**, on Darwin x86_64. The exact pinned-Node PATH is
included in each retained command. No dependency or lockfile change was made.

## Artifact hashes

All hashes below are SHA-256 of file bytes, prefixed by `sha256:` in the
machine-readable evidence.

| Golden | SHA-256 |
| --- | --- |
| Acceptance text | `9167c4d2f02556aff1c315b37fa8a8aabb9ba3261d11f3fd04d72fea7a0a806c` |
| Acceptance sidecar | `76d2e275acf81542f2c3749c4f69fbd3388eafd7b08f72e002c5f5aba632a57f` |
| Legacy text | `512411c39f8cbfc6cced6b64d931a3e4248b497028dbd3acd85d2849ca2917bf` |
| Legacy sidecar | `f9aa47ff7ad2713f39af39af5b83f9b98d68a5fb0b57eca029d36ac31f31d574` |

The accepted minimal input still hashes to
`660035aae5a6c8f75462b63ec5348e73bb95b93835d27e1654bdac67b08cc3ac`,
and the accepted torture input still hashes to
`18f6ea65aae8533a0b810bcef6a62f4ac6c8074ae594ad4a760b3ba68a45f36e`.

## Walkthrough and review checklist

1. Open `tests/data/issue_37/acceptance.prompter.golden.txt`: it starts with
   `(OC)`, displays a pronunciation cue, switches to `(VO)` before “as the fog
   rolls in.”, and returns to OC for the next sentence. The phoneme metadata
   and excluded direction/note text do not appear.
2. Open its sidecar: the first complete sentence is one `on_camera` beat with
   explicit ID ending `030`. The alias is visible, the phoneme value is retained
   with `visibleInPrompter: false`, and revision 37/text hash are recorded.
   The final VO sentence gets a deterministic UUIDv5.
3. Compare the legacy fixture/goldens: no new arrays are stored in the source;
   all three sentence beats are derived at revision 36. No beat numbers or
   section headings enter the text when their settings are off.
4. Review the [implementation plan](plans/issue-37-prompter-export.md) for the
   fixed sentence rule, punctuation/spacing behavior, cue escaping, metadata
   interpretation, and output safety. These are explicit implementation
   choices, not inferred provider behavior. Sentence detection is a frozen
   token-aligned default; explicit authored beat ranges override it.

These are review aids, not requests to repeat automated acceptance. The
deterministic checks are already retained. To reproduce locally with new
output paths in an existing directory:

```sh
rtk npm run validate
rtk npm run export:prompter -- tests/data/issue_37/acceptance.script-document.json \
  --text /tmp/prompter-review.txt --sidecar /tmp/prompter-review.json \
  --include-section-navigation --include-beat-numbers
```

The CLI will not overwrite files or follow an output symlink. It checks both
destinations before writing and uses exclusive creation. An I/O race/failure
can leave an explicitly reported partial artifact; it never reports that as a
complete export. All negative filesystem tests use temporary copies.

## Development corrections retained honestly

Initial bootstrap attempts encountered absent Vitest, an unpinned default
Node, and a PATH lacking uv; the final gates use the pinned runtime and locked
dependencies. Earlier interrupted/truncated runs are not counted as evidence.
Test-first regressions exposed punctuation-in-token sentence handling, leading
quote placement, unsafe revision/beat identity, and overwrite behavior. The
overwrite regression initially reached this slice's new fictional fixture
through a test symlink; it was restored from its authored data and the test
was isolated to a temporary copy before final verification. No accepted fixture
or private data was changed. Final golden bytes match the original candidates.
