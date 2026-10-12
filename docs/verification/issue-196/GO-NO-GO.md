# #196 cloud validation: go/no-go

**Qualification verdict: GO** for the eligible scope below (owner, 2026-10-12).
**Activation: NOT IN EFFECT.** The scoped edits to the policy and guidance
were denied by this session's permission classifier (see "Activation
blocker"). Until an authorized editor lands them together, local full
acceptance remains the rule for every ticket.

## What would be activated

A complete passing `Validate` run on GitHub-hosted `ubuntu-24.04` can replace
the Intel-Mac `VITEST_MAX_WORKERS=1 npm run validate` rerun. This applies only
to the eligible rows of the
[check-to-platform matrix](../../plans/issue-196-qualification.md#check-to-platform-matrix-proposed-activation-decides).
Every one of the following must hold. If any rule is broken, the ticket
falls back to the local full gate:

1. **The trust anchor is accepted `main`, never the candidate.** Run the
   validator and read the approved profile from a clean checkout of accepted
   `main` that contains this activation:

   ```sh
   node scripts/cloud-evidence-validate.mjs --repo mbelinkie/vera-script-to-timeline \
     --run <id> --attempt <n> --event pull_request --pr <N> --delivered <candidate-rev> \
     --profile docs/verification/issue-196/cloud/profile-qualified.json \
     --scope excluding-media-sensitive
   ```

   Exit 0 is required.
2. **The report must name the approved profile:** `profileDigest` =
   `1d6b3c41d0bfbba1c9e012796a1067ebba7944e6a8615ecf96e77444071257c7`, and
   `manifest.source` must name the run artifact, never `local-file`.
3. **The candidate must not touch the trust anchor or the qualified
   controls.** That means the profile or approval files, the evidence
   helpers, the workflow, manifests, lockfiles and tool configs. Any such diff
   is ineligible and takes the local full gate plus requalification. The
   validator rejects control drift itself; profile and approval edits are
   excluded by this rule.
4. **Scope:**
   - The durable activated scope is `excluding-media-sensitive`. It covers
     tickets whose diff touches no media-processing path, meaning FFmpeg or
     FFprobe callers, audio or picture rendering, or probing.
   - Choosing that scope is the owner's judgment, so the reviewer must confirm
     the diff qualifies.
   - Media-processing changes always keep their local slow-test exception.
5. **Runner images:** GitHub rolls hosted images about weekly, and apt
   `ffmpeg` is not version-pinned.
   - When the image differs from `20261004.327.1`, the evaluator suspends the
     `media-sensitive` scope. Full scope then fails closed, which is
     expected.
   - Pure-logic acceptance under `excluding-media-sensitive` is unaffected.
   - Reinstating full scope means requalifying the profile with two new runs
     and a new approval of the new digest. The owner may submit that as a
     deterministic profile update. It must never become a routine weekly
     Producer request; media scope simply stays suspended until someone
     chooses to requalify.

## Qualified profile (draft `cloud/profile-draft.json`, `qualified: false`)

- **Profile digest:** `1d6b3c41d0bfbba1c9e012796a1067ebba7944e6a8615ecf96e77444071257c7`.
  An approval must name this digest.
- **Command:** `VITEST_MAX_WORKERS=1 npm run validate`.
- **Controls:** 24 blob digests, among them:
  - the workflow and the evidence helpers;
  - root and package manifests, both lockfiles and `.nvmrc`;
  - `.python-version`, `pyproject.toml` files and `tsconfig*`;
  - `eslint.config.mjs` and `tests/conftest.py`;
  - the three nested `ruff.toml` files and the contract generator.
- **Runtime:** Node v24.19.0, npm 11.17.0, uv 0.12.5, Python 3.12.14, ubuntu
  24.04 x64, runner label `ubuntu-24.04`, image `20261004.327.1`.
- **Media:** FFmpeg/FFprobe 6.1.1-3ubuntu5 (package `7:6.1.1-3ubuntu5`).
  Binary SHA-256 `ed16af62…` (ffmpeg) and `272f6ebc…` (ffprobe); capability
  digest `41778d36…`.
- **Inventory:** pytest 499, Vitest 403 (repeated `it.each` names numbered),
  node:test 61.
- **Skip allowlist:** empty.

## Calibration evidence (round 2, tree `5eb5c6e808508b4973537fbe475693123870efe7`)

| Run | Event / checkout | Job | `npm run validate` | Result |
| --- | --- | --- | --- | --- |
| [38296397261](https://github.com/mbelinkie/vera-script-to-timeline/actions/runs/38296397261) | push / `d9c63a84` | 31:26 | 30:24 | GitHub success; evaluator pass at full scope |
| [38296403984](https://github.com/mbelinkie/vera-script-to-timeline/actions/runs/38296403984) | PR #198 / merge `cc0aa6fc` (parents `98b9a614`, `d9c63a84`) | 39:00 | 37:54 | GitHub success; evaluator pass at full scope |

The evaluations used a **hypothetical local approval** held only in job temp,
not a Producer approval (`cloud/round2-eval-*.log`). Both runs showed:

- no failures or suspended scope;
- no earlier attempts on this tree;
- pytest 499/499 with no skips, and identical plain and reporter collection;
- Vitest 402 + 1;
- node:test 6 + 23 + 32;
- no tracked-file changes, and a complete collection.

Remaining limitations:

- `checkout-attested` (PR) and `history-scope`;
- `outcome-by-step-only`: lint, type checks and generated-currentness come
  from the GitHub step conclusion;
- `parameterized-identity`.

Round 1 (`ea5db6c`) had two further complete green runs, which were refused
for the duplicate-name defect: [ROUND1.md](cloud/ROUND1.md). Across the four
runs, the job took 30–40 minutes with a queue of 3–4 seconds.

## Comparison with the #193 local reference (Intel Mac, `98847b97`)

- pytest: 499 = 499.
- Vitest: 402 + 1 = 403.
- node:test: 6 + 23 match. The 32 new #196 helper tests are the only addition.
- Product tests, fixtures and goldens are byte-unchanged since `98b9a614`.
- Local pytest took 54:03 on its own, against a whole cloud job of 30–40
  minutes. The real saving is freeing the Mac. No speed gate is claimed.

## Local exceptions that remain (never substituted)

- Control-file, dependency or lockfile changes need the local full gate, plus
  requalification.
- Media-processing changes need affected slow tests serially on the Mac's
  installed tools. Media scope is suspended whenever the Ubuntu media
  fingerprint drifts.
- #174's Mac media-tool qualification, real Resolve runtime, private media,
  transcripts and provider calls stay External and local.
- Listening, visual and design judgments stay with the Producer.
- Golden and fixture changes still need their approved change notes.
- Independent review and frozen-boundary audits still apply.

No private media, provider access, paid runners or new secrets are involved.
The public artifact is only the sanitized manifest, and both real artifacts
were scanned: no paths, transcripts, media names or environment data.

## Approval receipt

- **Instruction:** Producer, relayed by the coordinator on 2026-10-12. Quoted
  verbatim: "I approve 196 if Claude is happy with it". The coordinator holds
  the original consent privately.
- **Condition:** the #196 owner's honest GO, after all required evidence and
  review.
- **Satisfied:** yes. The owner reports **GO** on the evidence below. This is
  the conditional instruction only; no further Producer statement was made or
  needed.
- **Bound to:**
  - profile digest
    `1d6b3c41d0bfbba1c9e012796a1067ebba7944e6a8615ecf96e77444071257c7`
    ([cloud/profile-qualified.json](cloud/profile-qualified.json));
  - the calibration runs 38296397261 and 38296403984 on tree `5eb5c6e8`;
  - the scope and exceptions on this page.
- **Delivered branch head:** the final reviewed commit on
  `claude/issue-196-cloud-validation-prep` / PR #198. Its tree differs from
  `5eb5c6e8` only under `docs/`.
- **Not covered:** full media scope after an image rollover, any frozen,
  native or human gate, and any other ticket's acceptance.

After merge, evaluate the post-merge `main` push run against the profile, at
no cost: the merge changes no control. That evaluation is the first
in-production check, once activation is in effect.

## Evidence behind the GO

- **Cloud qualification:** two complete same-tree runs from round 2, both
  accepted at full scope (above). Two further complete green runs from round 1
  were refused only for the duplicate-name defect, which is now fixed.
- **Local full gate on `289a080`** (tree `173fb6e6`, the tested revision; it
  differs from calibration tree `5eb5c6e8` and the delivered tree only under
  `docs/`):
  - command `PYTEST_ADDOPTS=--durations=25 VITEST_MAX_WORKERS=1 npm run validate`;
  - exit 0, started 20:13:45Z, finished 21:13:06Z;
  - Node v24.19.0, npm 11.17.0, uv 0.12.5, Python 3.12.14, Intel macOS 24.1.0;
  - generated-currentness, lint and types clean;
  - Vitest 402 + 1, node:test 6 + 23 + 32, ruff and format clean (389
    files), mypy clean (111 files), pytest 499 passed in 58:02;
  - no tracked files modified;
  - `package-lock.json` SHA-256 `e615667b…`, identical to #193's reference;
  - retained as `validate-final.{metadata,log,exit,finished}`.
- **Retained failed check:** the delta `validate:fast` run at 19:12Z, which
  hit 8 Vitest 5000 ms timeouts under host load 24.9. It is classified in
  CHECKPOINT. Its delta is covered by the passing local full gate above.
- **Reviews:** the main delta (approve with fixes, applied), the duplicate-ID
  delta (approve) and the final revision (GO with fixes, applied). See
  [independent-review.md](independent-review.md).
- **Docs-only differences:** tested, calibration and delivered trees differ
  only under `docs/`. The only check that reads `docs/` reads
  `docs/verification/issue-179/`.

## Activation blocker (exact denied actions)

The auto-mode permission classifier denied these, and none was bypassed:

1. **Policy and playbook edit.** Adding a "Qualified cloud substitution"
   section to `docs/VERIFICATION_POLICY.md`, and a playbook row to
   `docs/PROJECT_OPERATING_PLAYBOOK.md`, were denied:
   `[Instruction Poisoning]`.
2. **Guidance edits withdrawn.** The matching edits to AGENTS.md, CLAUDE.md,
   README.md and the coordination SKILL were accepted at first. After denial 1
   they would have pointed at a policy section that doesn't exist, so the
   owner withdrew them (`git restore`). A follow-up read of `5ab39b2` was
   denied: `[Self-Modification]`.
3. **Earlier in this issue:** the execution-phase issue comment and the board
   status write (`[External System Writes]`), and the `5ab39b2` pointer
   cherry-pick (`[Instruction Poisoning]`).

To complete activation, an authorized editor (Producer or coordinator) applies
these together:

- **`docs/VERIFICATION_POLICY.md`:**
  - Replace "Full acceptance still requires the local locked-toolchain gate.
    CI continues unchanged; a CI pass is not yet an approved substitute for
    local acceptance." with "Full acceptance still requires the local
    locked-toolchain gate, except within the qualified cloud scope below."
  - Add a "Qualified cloud substitution" section containing rules 1–5 of
    "What would be activated" above. Those rules are: validator and profile
    from accepted `main`; digest `1d6b3c41…` with an artifact-sourced
    manifest; eligibility excludes controls and media paths; the other gates
    stay; requalify, never self-certify.
- **AGENTS.md, CLAUDE.md, README.md and the coordination SKILL:** add the
  `5ab39b2` policy-pointer paragraphs, plus one sentence: "Within the policy's
  qualified cloud scope, a complete CI pass accepted by the validator from
  accepted `main` replaces the local full rerun."
- **`docs/PROJECT_OPERATING_PLAYBOOK.md`:** add one "Qualified cloud
  regression substitution" practice row.

## Not done by this page

- No merge, close or roadmap transition.
- No change to the issue comment or the board. Those writes were denied in
  this session.
- AGENTS, CLAUDE, README and skill pointer edits were also denied
  (instruction-file classifier).
