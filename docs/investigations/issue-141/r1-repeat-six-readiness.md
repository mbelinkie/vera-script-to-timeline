# R1 repeat package readiness

## Local status

Ready for review and later isolated registration. This work adds dispatcher
actions `r1-repeat-reopen` and `r1-repeat-duplicate` through `run(resolve,
config, *, probe)`. It made no registration or Resolve call.

## Pins

- Private injected probe snapshot:
  `out/issue-141-observation-20260930-01a0f318/r1-repeat-six-probe-snapshot-54bbbeee926a.py`,
  SHA-256
  `54bbbeee926a5ef423615b1f981ec8ebe6586e91f938a8aad05db441ecc53310`.
- The snapshot was copied byte-for-byte from `docs/investigations/issue-141/probe.py`
  at that hash. The live probe may acquire later dispatcher registrations; the
  repeat package continues to use only this non-symlink snapshot.
- Full-pair reader: `r4-range-repair.py`, SHA-256
  `9b6977747a1f3decf957ead6134f10fc4f597bf9d0c3dc5c081b7bf2671879a4`.
- Local action package: `r1-repeat-six.py`, SHA-256
  `4aece3d8ab7c7e0ab215fc9eb841fc95b56b85fb0809859e7f587ce83b0e2c28`.
- Offline adapter check: `r1-repeat-six-check.py`, SHA-256
  `d7c67287088cab9e3a8df5a37e0022e7bc919dbca0d52c5edc7a00b5848878cf`.
- Six-timeline reference pair:
  `out/issue-141-observation-20260930-01a0f318/protected-six-r4-pool-20261001T180848.009764Z/pair.json`,
  SHA-256 `5131589527428829afe6e1503e245609a4f17bb3207a2fe61a874db4289601b3`.
- At invocation, `repeatCheckpoint` must name a fresh selected-Matrix pair
  directly inside `outputDir`; `repeatCheckpointSha256` pins its bytes. The
  actual checkpoint is intentionally supplied per run rather than guessed.
- `repeatExpectedContext` must exactly match the observed product/version,
  project UID/name, Edit page, idle state, empty queue, Matrix selection,
  playhead, selected-item evidence, and track-lock reads.

## Checks

- `ctx-wire run rtk proxy /usr/local/bin/python3.14 -S docs/investigations/issue-141/r1-repeat-six-check.py` — passed.
  Fake `run` executions succeeded for reopen and duplicate; the duplicate
  retained complete seven-timeline pairs tagged `protected-seven` and preserved
  the original six. Fake refusals covered bad hash, changed Edit context,
  nonempty render queue, wrong project UID, and wrong inventory before mutation.
  The same check imports the pinned snapshot, verifies its bytes and non-symlink
  status, confirms the reader pin, and confirms the private probe `ROOT` is the
  repository root after import.
- `ctx-wire run rtk proxy /usr/local/bin/python3.14 -S -m py_compile docs/investigations/issue-141/r1-repeat-six.py docs/investigations/issue-141/r1-repeat-six-check.py` — passed.
- Fake execution confirmed the package's original six-UID map stays unchanged.

## Boundaries

The seven-timeline path privately loads the hash-pinned probe snapshot and
full-pair reader, then extends only those in-memory identity maps after
observing exactly one new UID with the required repeat name. After the snapshot
import, its private `ROOT` is rebound to the actual repository root so its
path-sensitive output guards remain correct. The reader's full timeline, item,
source, and pool collectors remain in use.

The External Scripting `None` value remains an operator-supplied config
attestation because Resolve exposes no getter for that preference. Usage/cache
and active/inactive getter differences remain reported as observed; no lineage
claim or guessed normalization is made. No native evidence exists yet; the
operator must supply the fresh checkpoint hash and run the selected action
after the preceding recovery work.
