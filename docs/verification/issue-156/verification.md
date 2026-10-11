# Issue #156 — retained design verification

This directory verifies a documentation proposal and the unchanged baseline.
It does not qualify v2 contracts, prepared media or Studio behavior.

- [Source pins](source-pins.json): 33 exact source revisions, byte counts and
  SHA-256 digests. STT sources were read from Git objects; four Research sources
  from the authenticated GitHub Contents API at the published revision. No
  private source media or Research data was read or changed.
- [Design checks](design-checks.json): actual source/interface checks, finite
  package DAG, rational arithmetic and sampling/bounds assertions, local
  artifact references and documentation-only/frozen-boundary audit. The small
  read-only checker is retained locally under ignored `out/issue156/`; its
  command and hash identify it without adding product code to this plan slice.
- Independent review: bounded Luna inventories of current STT and Research
  interfaces, followed by an independent plan review. Audio-level and
  nonzero-origin findings were corrected; the final requested migration cases
  were added. Review does not substitute for implementation tests or Producer
  acceptance.

The final Luna recheck passed after the migration cases, public v2 import
names and playback-gain/cache-key distinction were added. It found no
remaining interface/ownership contradiction in those corrections.

Repeat the baseline gate with the repository's locked runtime:

```sh
ctx-wire run rtk npm run validate
ctx-wire run rtk git diff --check
ctx-wire run rtk git diff --exit-code 96978919616df0148d9c4b06781aeb80acfa85e4 -- contracts fixtures packages python tests scripts package.json package-lock.json pyproject.toml uv.lock
```

Use Node 24.19.0, npm 11.17.0, Python 3.12.14 and uv 0.12.5. The exact completed
command, result, counts, versions and local log hash are retained in
`design-checks.json`; do not infer a pass from this recipe. Toolchain/dependency
setup is local and ignored; lockfiles and product files are unchanged.

Future deterministic and actual-application gates are defined in plan §8;
those proposed test files do not exist at this baseline. The Producer review
and separate change-note approvals are in plan §§9–10.
