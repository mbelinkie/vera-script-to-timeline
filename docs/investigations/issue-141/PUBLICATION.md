# Reviewing the published #141 and Workflow Integration evidence

Start with [report.md](report.md), its positive-case/build/owner matrices, [final-findings.md](final-findings.md), and [the 41-title evidence index](../../../output/issue141-per-title-evidence-audit.json). [The second-opinion handoff](second-opinion-handoff.md) keeps the original procedures and failure chronology. #141 is open pending producer review; #149's investigation is accepted and Done.

## What is committed

- Original #141 preparation/editorial evidence, including [editorial-macro-plan.md](editorial-macro-plan.md), [matrix-finalize-success](evidence/matrix-finalize-success/), the operation captures, journals, comparison records and final seven-timeline review.
- Full retained #141 run records under `out/issue-141-observation-20260930-01a0f318/`, including synthetic source fixtures/output and analysis. Protected producer source media bytes are excluded.
- #149's [WI W1–W7 scripts and result records](../issue-149/workflow-reruns/) and [five-case discriminator records](../issue-149/workflow-discriminators/), with both owned `out/issue149-workflow-*` runs, raw snapshot pairs, render receipts, OTIO exports, analysis, synthetic sources and rendered output.
- [publication-manifest.json](publication-manifest.json) indexes every retained payload with original-local, published and decoded-public SHA-256 values. [verify-publication.py](verify-publication.py) verifies the committed payload and can extract the logical files.

The original local records were copied into a separate publication worktree; they were not overwritten. Private home/worktree paths are consistently replaced by `REPOSITORY`, `LOCAL_DASHBOARD` or stable `LOCAL_PATH` aliases. Equality/difference comparisons still see the same alias for the same original path. Report corrections change recommendations, not native outcomes. Large files use deterministic lossless gzip. No evidence field, observed result, UID, range, word measurement, render job or timestamp is fabricated by publication.

**Hash interpretation:** `originalSha256` identifies the private, pre-publication file retained locally. Sanitized text has different bytes. `publishedSha256` authenticates the committed file, and `decodedPublishedSha256` authenticates its decompressed content. Binary synthetic media is preserved losslessly; its decoded public hash can be compared with the original media hash. Historical raw/source hashes in result JSON and script-pin guards remain historical audit values; they must not be presented as hashes of sanitized scripts or records. Markdown rows updated for this correction are marked `editorialCorrection` in the manifest.

## Verify or extract without Resolve

From a fresh checkout of this PR, run:

```sh
python3 docs/investigations/issue-141/verify-publication.py
```

This checks every manifest file, its stored and decoded hashes, and removed private home paths. It does not execute a native test. To expand the archives into a **new** directory for normal JSON/media inspection:

```sh
python3 docs/investigations/issue-141/verify-publication.py --extract /tmp/vera141-review-NEW
```

Large records have `.gz` added to their committed name; extract restores the original logical name. Sources already archived as `.json.gz` are decoded once at their logical location. The manifest is the authoritative original-to-public path map; raw historical records may name logical paths or original checksums. Current report Markdown links point to committed archives where necessary.

## Reproduction boundary

Archived collectors, launchers and action configs document what was actually run. They are **not turnkey commands against a current Resolve project**: private paths are aliased, source hashes refer to original versions, UIDs are pinned to historical projects, and configs may describe already completed actions. Never replay them against retained projects. For an independent native experiment, create a new authorized disposable synthetic project, establish fresh fixture/source/hash/UID pins and one new action receipt, and follow the handoff's complete-pair/single-dispatch protocol. Keep External Scripting None and record the actual build/entry point. This publication runs no new native test.

The two timelines with the producer's real clip remain metadata/transcript evidence only. No protected source media file is committed or read for this publication. Read the approved transcript correction and source-versus-program distinction before using those observations.

## Protected transcript exception

The full-source producer transcript probe directories are deliberately withheld. The manifest lists each omitted record and reason. Approved 22/19-word derived comparison, expectation correction and independent/dispatch reviews remain published. Their original raw-source hashes are historical provenance, not publicly verifiable payload; do not claim independent authentication of the omitted full-source transcript. All synthetic editorial/WI records and their owned outputs remain published.
