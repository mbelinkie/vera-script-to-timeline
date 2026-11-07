#312 adopted PR #323 — read-only restart ledger and bounded remainder

Audit snapshot: 2026-11-07 04:58 UTC. This is a **read-only reconciliation**, not native authorization, a new benchmark, or evidence of issue acceptance.

## Ownership and immutable starting point

- Original issue #312 and draft PR #323 remain open. The PR is **not merged**, and its GitHub API metadata reports mergeable=false (main has moved).
- Original source branch: codex/312-script-to-resolve-overhead. Pinned head: c3682476ceef8bc1ccd4a7172f05691dbf24e47f. The original Mac worktree is at ~/.codex/worktrees/f861/VERA Script to Timeline; **do not change or reset it**.
- Continuation: zodex/312-adopt-pr323 in .worktrees/pipe-312, already locked as "vera adopted PR". The conductor alone fast-forwards the **existing PR branch** after checkpoints; no second PR, push, merge, source rewrite, or old-target replay.
- Reviewed issue.md's latest paused handoff, adoption.md, progress.md, original PR description/evidence, the pinned PR diff scope (26 changed files, 3,120 additions/61 deletions), and the #448 queue design in origin/main. The original diff includes fixture/speech/package tooling, performance counters, workflow hashing, target/render-root guards, and focused tests. No prior commit or fixture was recreated.

## Historical evidence that must remain intact

These are **previously reported**, not independently rerun during this audit:

| Already delivered on original PR | Historical evidence / acceptance limit |
| --- | --- |
| Public synthetic fixture | 30 narration rows, 60 picture placements, 12 overlays, 24 synthetic video sources; rights/alignment and frozen inputs reported in earlier issue checkpoints |
| Supported six-row native rehearsal | 21 events / 21 media, saved/reopened, zero discrepancies; 77.684730 s; not a timed baseline |
| Three warm baseline/candidate pairs, unchanged | Median named VERA overhead 607.630 s to 241.494 s (-60.26%) |
| Three warm baseline/candidate pairs, one-row edited | Median named VERA overhead 633.089 s to 249.421 s (-60.60%) |
| Six candidate full-fixture saved/reopened deliveries | 102 events, 68 media each, zero discrepancies; PR claims continuous-wall nonregression |
| Cold unchanged | 2,546.849 s outlier with 99.95% attributed to package validation/hashing; **no cold speedup claimed** |
| Code and review | Bounded four-worker file hashing, currentness and symlink guards retained; two Claude-identified retry defects fixed by pinned head c3682476 |

The original PR description supplies those aggregates, **not the raw observation report**. The raw retained benchmark report was not located in the pinned tracked files or in the original Mac worktree's issue312 directory by filename search; retrieve, inspect, hash and preserve it before any further timed work or final publication. Do not reconstruct raw rows from medians or re-run completed forward measurements. The original four-hour cumulative timed-work counter therefore remains **unverified**.

## Live host read-only inspection: actual versus historical

Inspection used only Mac shell metadata, read-only SQLite snapshot and read-only Resolve scripting getters. No target, native request, project selection, render, queue or file was mutated.

| Subject | Historical paused state (issue handoff) | Observed 2026-11-07 04:58 UTC | Eligibility |
| --- | --- | --- | --- |
| Resolve current project | R2 isolated UID prefix 71d6cc73, timeline prefix a8513726, persisted 24000/1001 | Resolve process present; read-only GetCurrentProject reports **Untitled Project**, UID ef6a50a4-915a-4657-9d16-55653f48a01f. Historical R2 is **not selected**, so its current timeline UID/rate cannot be certified without changing selection. | **No action** against R2 or current project. Preserve both. |
| R2 pristine native chain | 1,407 frames, 11 items, six tracks, 38 effects; verified construct/save/reopen; capture_pre result prefix 1f0f36c6 ingested with committed prediction | Historical handoff only; its original full ledger/result hash and selected-project identity not reauthenticated. | Preserve the operation as consumed; no replay. |
| R2 edited/rebuild | No matched same-target edited chain at pause; separate edited project did not count | No new #312 native outcome found in the inspected running process list; absence of a process does **not** certify a historical UNKNOWN operation terminal. | Genuine matched proof still open. |
| Earlier B/C and G/CleanU/P1 targets | Old B output consistency; C rebuild; G/CleanU/P1 partial/uncertain/expired; P1 refused at persisted 24.0 fps | Old original worktree issue312 directory survives, with 8 request.json and 6 result.json files; target B/C sessions still exist; original R2 evidence is **not** among those older on-disk snapshots. | All old requests, approvals, targets, UID pairs and source artifacts **reserved forever**. |
| Original Mac worktree session identities | Prior B/C output qualifications, separate from R2 | B pristine/edited session target project UID a581802b-f0fb-4482-9659-ba037eec7f71, timeline UID 91d4486a-f5a1-4df1-ae3f-6aec6375a542; C rebuild target project UID 709bc8ff-b33c-4f14-bc24-16369b1afb31, timeline UID e50a91df-681f-4875-a315-a14b51bfabf5. These are **not** the R2 proof. | Never reuse. |
| External media/DRP | /Volumes/Family 1A/CodexRulz/vera-issue312/VERA312-R2-durable-20261027.drp | /Volumes currently lists only Macintosh HD and Family 1B Backup JBOD; **Family 1A is not mounted**, so the DRP, external package/media and evidence hashes are unverified. | No render, rebuild or native setup until correct volume and exact bytes are available. |
| Internal free space | Stop below 40 GiB free, or on rapid decline | df shows roughly 26–27 GiB free (28,039,228 KiB on / at 04:58 UTC), **below the hard floor**. | **Hard stop on heavy/native work.** Do not clean existing outputs. |
| #448 durable queue | Qualified 8/8 campaign; standalone launchd worker and phone monitor | Read-only immutable SQLite snapshot of issue-448/pilot-rebuilt-p2/queue shows campaign resolve-campaign-7a818136c76149aeaa451d400c5f937a terminal completed_verified and **8 jobs completed_verified**, no queued/running jobs in that DB snapshot. Periodic #447/#448 worker processes can still appear transiently. | Queue exists, but this snapshot does not authorize a #312 run or prove global exclusivity. |
| Other outstanding native state | Older paused/UNKNOWN operations must not be replayed | No matching #312 executing process in sampled pgrep; full output-host chain (178 attempt directories) was **not cryptographically reconciled**; read of this history failed. Other queues/owners must be checked again just before any submission. | Treat historical UNKNOWN as UNKNOWN, never as complete or free for reuse. |

Read-only sample request SHA-256 identities in the original Mac worktree, retained and never eligible for re-submit:

- rehearsal-release-v1 = 91767b9b8d1bb50ad3cdd2f9b7f4c5fb8e8caf771113eecf0ffaab674e260e89 (consumed/failed historical);
- rehearsal-release-v2 = 8af519ce1bd34969233c682182c1e6bdbe639accc2d6ca008b93dc1b3c80411e (historically prepared-only, now stale; **do not dispatch**);
- rehearsal-release-v3 = e841bc4699b30c7129359d48d436540eb3413f3471f850b3b08f7833dbd5c956 (consumed, verified rehearsal);
- reverse-proof-v2/pure request digests = 3dc24d87489a19960520daf03c01b7e0488bcfdf2c73d84a8089a616d6ccdba2, 5b77ed42fb526ba6d747508d017c56a90fd10c1e3dd07368c70e15204196db98, bde13bc03a8e2c8ab992d6b6cb1d4f23552b11339a19fca554fbe86ab1bbff15, 6ea946001c30e168456819dad3de29db5c521a28fd28c5e52ee330b206ca3d23, a6f518e85517f94fbc09f04e8cb6e6cde2257a7db9ceb122a9709b93aa4ca4ff.

Those eight hashes are a **partial local inventory**, not a reconstructed R2 host journal. Other installed request archives, used operation UUIDs, host signatures, and UNKNOWN chains must be verified under the actual native owner's existing read-only tooling. Never conflate an SHA with a fresh authorization.

## Remainder acceptance matrix

| Gate | Status at restart | Proof required before claiming done |
| --- | --- | --- |
| Original public fixture, rights, rehearsal | PR/history claims delivered; original bytes preserved | Retain pinned rights/manifest/generator digests; do not regenerate; audit only if source discrepancy found |
| Warm forward optimization and six saved/reopened full builds | PR reports delivered (-60.26% and -60.60%) | Locate retained raw report; verify identity, numeric target frozen before optimization, continuous total, medians/ranges, 102/68 readbacks, and work counters; **no rerun** |
| Cold performance and attribution | PR reports outlier; no speedup claim | Preserve raw cold observation and >10% regression analysis |
| Matched reverse pristine and +24-frame edited proof | **Missing** on identical project/timeline | 1,407-frame supported three-row companion; boundary 327 to 351; real captured before/after, host-authenticated readback and same target UID, genuine inference/decision, accepted script revision, fresh separate verified rebuild and PCM proof |
| Three reverse pristine plus three reverse edited observations | **Missing** | Six distinct native-qualified observations, comparable timings and readback, raw rows and named reverse spans; median/range/n counts; correct attribution; no surrogate observations |
| Native ownership/storage/integrity guards | **Not cleared for new action** | Mounted correct external volume, digest-checked DRP/assets, >40 GiB internal free, no rapid drop, actual R2/other operation reconciliation and new authorized disposable target, exclusive queue |
| Current-main integration, pinned checks and adversarial regression | Pending | Preserve original PR work while integrating main, test hash/source/target/auth/CAS/PCM guards with Node 24.19, focused checks and npm run validate:fast |
| Independent review, exact-head CI, PR #323 delivery, External close | Pending | Required Claude re-review after final integration, exact-head green GitHub CI, deliberate existing-PR merge to main, then actual real-app evidence and External closure; no automatic waiver or earlier Done |

## Finite declarative reverse campaign (NOT enqueueable yet)

The supported reverse companion is 1,407 frames at 24000/1001, two generated held slates, first three genuine measured rows, 11 events, six tracks, required source-rate/resolution coverage, and a held boundary at frame 327. A real supported edit moves that boundary +24 frames to 351, **without** changing program end, narration or timing authorities; inference must produce a legitimate accepted revision.

**Critical adapter mismatch:** merged #448 M3 accepts 1–100 cases and up to 200 trials, but a child is an M2 native.v2.guarded_build with exactly **one new disposable target**. Its validator rejects duplicate target/request/evidence identities across children. It does **not** by itself drive the multi-step same-target pristine capture → edited capture → authentic inference/accepted revision → fresh rebuild chain. A matched proof cannot be fabricated by putting pristine and edited in two independent M3 children or by attaching a saved result from a different target. Before execution, phase 2 must prove an existing guarded queue-compatible path for that sequence or make the **narrowest** bounded adapter extension with security/identity tests; otherwise report the unsupported capability, not PASS. This does not authorize restoring or operating a historical target.

**Finite reserved names / logical IDs** (reservations for documentation only; not queue IDs, native operation UUIDs, approvals or manifests):

| Order | Logical trial ID | Case ID | Intent | Required native truth |
| ---: | --- | --- | --- | --- |
| proof | vera312-proof-01 | vera312-matched-reverse | One bounded same-target proof and separate rebuilt target | fresh 23.976 project/timeline, pre/post captures, actual +24 edit, accepted script revision, independent verified rebuild, PCM consistency |
| 1 | vera312-rp-01 | vera312-pristine | Pristine observation 1 | fresh one-use request/target and authenticated native proof |
| 2 | vera312-re-01 | vera312-edited | Edited observation 1 | real supported edited path, never hand-authored evidence |
| 3 | vera312-re-02 | vera312-edited | Edited observation 2 | independently authorized one-use native proof |
| 4 | vera312-rp-02 | vera312-pristine | Pristine observation 2 | independently authorized one-use native proof |
| 5 | vera312-rp-03 | vera312-pristine | Pristine observation 3 | independently authorized one-use native proof |
| 6 | vera312-re-03 | vera312-edited | Edited observation 3 | independently authorized one-use native proof |

For the six observations, campaign name vera312-reverse-six-v1, two case IDs above with comparisonKey vera312-reverse-companion-v1, **fixed explicit** order as shown (P/E, E/P, P/E), single variant, warm cache mode, rounds 1–3 per case. M3's alternating mode is for baseline/candidate *within the same case*; it is incorrect here because pristine and edited are different conditions. Each child must have a new verified pinned source commit, canonical plan SHA, unique request/target/evidence IDs and actual #448 v2 plan generated later. **No fabricated request SHA or native UID has been assigned in this audit.**

Ceilings: at most **900 seconds and 4 GiB per new trial**; six observations at most **5,400 seconds / 24 GiB aggregate**; one distinct proof attempt at most **900 seconds / 4 GiB**. Seven slots total at most **6,300 seconds / 28 GiB**. Never silently retry a refused/UNKNOWN/partial trial; follow queue's fail-stop semantics. The **entire issue's original timed benchmark ceiling remains 14,400 seconds inclusive of all earlier timed forward observations**, not a fresh four-hour allowance. The actual already-spent cumulative ledger is unavailable at this audit; before submitting any timed job, recover and authenticate it and enforce max(0, 14,400 - verified prior timed seconds), plus parent/child and disk caps. If this budget cannot cover all required observations or mounted external capacity is insufficient, **stop and report a measured limitation**, not fewer fabricated or cherry-picked passes. Proof/setup versus timed observations must be categorized before execution, never reclassified afterward.

Submission gate (all required): recover full raw forward budget; inspect every old original native request/result and R2 host chain for consumed/REFUSED/UNKNOWN; verify R2 backup and media SHA/actual mount; verify selected-project identity safely without LoadProject or historical mutations; confirm all render jobs terminal and native lock/quiescence; restore internal free space above 40 GiB without deleting evidence; validate queue adapter capability; issue **fresh** signed one-use requests with distinct disposable target/project/UUID identities; validate exact prepared plans and cumulative limits; only then enqueue once through the persistent #448 worker, disconnect supervising chat, and read report by campaign ID later. No new worker, monitor, sleep-prevention command, or native action in this phase.

## Result of this phase

**Audit disposition: NOT NATIVE-ELIGIBLE.** The current project does not match R2, the historical source volume is absent, the internal disk is below the required floor, the R2 host ledger and raw benchmark budget are not fully accessible, and M3's existing guarded-build adapter does not prove a same-target reverse chain. This is a preserved, actionable restart ledger—not a release, an acceptance check, or permission to replay. All legacy targets and the original PR/branch remain untouched.

Producer follow-up: Matthew will reconnect the external drive when native testing needs it. **Do not request the drive during phase 1**; prepare offline first. Once phase 2 reaches the mount gate, ask for the correct `Family 1A` volume only if it is still missing. Independently restore the internal free-space safety floor without deleting any historical #312 evidence before submitting work.
