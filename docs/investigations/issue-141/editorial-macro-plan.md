# Issue 141 — proposed bounded editorial menu macros

Status: producer approved the bounded editorial macros; the genuine R1 razor
and exact temporary-context restoration are verified. Approval text: “I approve the bounded editorial macros
for the VERA Issue 141 Synthetic Probe project.”
The current Hammerspoon authorization covers the observation launcher. This
proposal extends it to named editorial commands only in the approved synthetic
project, after injected native guards prepare and verify one exact case.

Read-only native menu inventory found these exact installed paths. The macro
uses no mouse coordinates, keyboard shortcut assumptions, arbitrary Lua input,
or other application. It dispatches one named command, then stops for injected
readback before any further command.

| Macro | Exact installed path | Required native precondition |
|---|---|---|
| timeline-start | Playback → Go To → Timeline Start | Exact Matrix project/timeline; full content must remain unchanged and playhead0 must be read back |
| deselect | Edit → Deselect All | Exact Matrix project/timeline and pinned content |
| select | Trim → Select Nearest → Clip/Gap | Fixed case playhead; unrelated tracks locked; verify exact selected UIDs afterward |
| split | Timeline → Split Clips | Only the target linked V1/A1 or named single-track occurrence selected; fixed playhead |
| trim-end | Trim → Resize → End to Playhead | Only R1-trim linked pair selected; playhead at captured end minus25 frames |
| nudge-right | Trim → Nudge → One Frame Right | Only the named R1-move/R5 linked pair or unlinked R2-offset occurrence selected |
| copy | Edit → Copy | Only R1-copy linked pair selected; retained copy source IDs |
| paste | Edit → Paste | Playhead in the reserved empty R1-copy space; all target tracks/layout verified |

The first live editorial test is only R1-razor: selected Matrix UID
29ae8331-b86e-4041-a548-960695cc7b24, case start1500, split at1600
(00:01:04:00 at25fps). The injected step retains original playhead/track locks,
locks V2/V3/A2/A3, sets the fixed playhead, and captures content before menu
selection. After select, native GetSelectedClips must identify exactly the
captured V1/A1 pair before split. If selection fails, restore only the recorded
locks/playhead in the verified context and stop. After split, require two exact
source ranges per target track and no other content change before continuing.
Retain actual child UIDs, markers/custom data and link groups; do not infer
lineage from copied metadata. Restore only locks/playhead; retain the real edit.

Later commands use separate matrix sections after that calibration succeeds:
R1-trim at500; R1-move at1000 with25 individually journaled one-frame nudges;
R1-copy at2000 with paste at2250; R2-offset at5000 with one nudge on unlinked A1;
R3-Graphic at8500/local100 with V3 preserved; R3-boundary at9000/local100,
capturing base split first and crossing A3 bed split separately. Each selection
and content mutation has its own before/after native evidence and no automatic
retry. Other timeline contents, source bytes and project settings are guarded.

Speech interval cuts remain separate reviewed native deletion steps: use actual
blade-produced interval UIDs, supported Timeline.DeleteClips with rippleFalse,
and exact before/after captures. No appended replacement clips substitute for
trim, move, blade, copy/paste or speech removal. Mute/solo and sample-precision
UI probes need separately named actions after this menu calibration; they are
not included in the present helper.

If the application/project/selection/content guard fails, stop and retain the
partial state. Do not undo, retry, clean up, operate another project, change
External Scripting, or dispatch arbitrary menu paths. The user's existing
None/synthetic-only attestation persists. External evidence remains required;
a passing helper fake proves only its dispatch guard, not editorial behavior.

Read-only Hammerspoon check after approval found `Timeline → Split Clips`
enabled in the exact synthetic project; `triggered:false`. Selection and full
state must still pass the native preconditions before an editorial launch.

The first actual selection-only run used Select All Clips Under Playhead. It
selected five case-local occurrences, including locked V3/A2/A3; full content
remained unchanged and the split guard refused before dispatch. The narrower
installed Select Nearest → Clip/Gap selection path will be checked separately,
after Deselect All. This changes only how the approved selection action finds
its target. The exact V1/A1 selected-UID guard remains mandatory; no lock-based
assumption licenses splitting the extra selections. The native selection
reader uses the documented list return, not a dictionary.


The05:48 launcher refusal occurred before menu selection. It was disarmed and
retained; a separate focus-only check matched the same project window and a
new read-only native capture at05:53 equals the complete verified restoration
byte-for-byte. No data mutation was dispatched. A newly staged preparation
from that verified checkpoint is permitted under the standing autonomous
authorization; no setter/menu execution is replayed. The no-retry stop rule
continues to apply to dispatched or uncertain operations and unrelated data drift.

While the producer decision on the stopped AV checkpoint remains pending, local-only preparation advanced. The existing helper now prepares the exact R2-linked pair at2500..2699 with split playhead2560 (local60); focused fakes cover target IDs, locks, playhead, restore and refusal. No R2 native/menu action is staged or run. The new R1-copy evidence checker accepts only two new-UID copies at2250..2449, reciprocal new links, identical source/marker/range data except record position, and exact source Usage+1; it rejects copied old IDs, source retargeting and unrelated pool changes in its local check. This is guard preparation, not live Copy/Paste or word-removal evidence. Root separately synchronized module hashes and passed reader, dispatcher and Ruff checks while keeping the private launcher disarmed.


Final local guard review: see the 09:00 UTC operator record and frozen source
manifest. Residual cuts and Graphic/base/A3 gates now have focused checks,
including the authored section marker and preceding base-split/restoration
binding. This is local preparation only; all native continuation remains
held at the stopped Copy/Paste checkpoint.


## Independent-test continuation authorized — 2026-10-01

Producer direction: a failed test does not complete the goal; determine what
works and what does not, then produce the full report. Producer approved
continuing independent synthetic sections while preserving stopped Copy/Paste
clips/metadata and restoring only each new test's own recorded context.
The earlier whole-investigation hold was too broad; only the stopped case and
stale audio candidate remain held. No Copy/Paste retry or cleanup is authorized.

Next bounded probe: R2-linked in Matrix2500..2699, fixed cuts2560/2570,
exact V1/A1 selection and child/source/Usage checks before one non-ripple
interval deletion. Retain all other timelines/cases, source bytes and Out
metadata. Start with four secondary locksTrue and playhead2250; after the
new case, restore only that same recorded context. Local guard changes touch
only the issue-owned helper/checker and source pin; no contracts, accepted
fixtures, production code or dependencies. Fake checks and Ruff pass.
Actual speech omission/routing/sample claims still require output evidence.

A first read-only menu launch refused before selection on its post-focus
window-title guard; no injected result was created. A separate read-only
Hammerspoon context check afterward matched the exact synthetic title in both
main/focused windows. This is a launch precondition refusal, not an API finding.
Launcher was returned to observe. Do not replay an uncertain mutation.


## Bounded Auto Select setup — 2026-10-01

Retained R2 attempts selected nothing and restored their own context without cutting. The installed manual documents Shift-V/Select Nearest Clip-Gap as playhead-based and identifies Auto Select as overlapping-track scope. Under standing approved synthetic preparation/editorial macro authority, add only exact named Timeline > Auto Select > Auto Deselect All Tracks plus Auto Select/Deselect V1, A1, A3. Use all-off followed by the named target tracks to establish deterministic synthetic selection setup; no arbitrary track/path. This UI context is not exposed by the full reader and menu tick fields are not reliable, so retained command journals plus exact selected-UID readback are mandatory. Keep that explicit setup for later synthetic cases, reset each new case to the reviewed V1/A1 Auto Select setup afterward, and restore only its recorded data locks/playhead. Full content/source/Out equality remains required. No split unless exact target IDs pass. This is an explicit test setup change; it does not restore or alter stopped Copy/Paste clips/metadata. Fake path/identity/focus/refusal checks pass before any dispatch.


## Return to Edit after queued-render recovery

The next editorial readback refused its Edit-page precondition after queue recovery. Read-only menu lookup verified Workspace > Switch to Page > Edit exists and is enabled on the exact synthetic project. Added only that fixed `edit-page` context command under the existing app/project/focus guards, with fake path/refusal checks passing. Its one dispatch must be followed by complete native unchanged-state readback before any editorial preparation. This is an authorized context change; no settings, content, timeline selection, save or queue action.


## Exact unlink preparation review, without setter replay

The R2-unlinked 12:14 native preparation changed only intended links/locks and target-video GetSpeed.PitchCorrection=True toNull. The shared preparation model now pins that exact optional field transition for the known single-track unlink cases; all other fields remain exact and unknown is preserved. A new read-only `editorial-case-review-preparation` binds the original refusal result/journal hashes, complete prior and prepared pairs, exact successful setter sequence/targets, and fresh complete live pair/playhead. It retains the original refusal and creates a new native reviewed preparation with its provenance and raw review pair; no setter/menu/save replay. The output-only sequencer can continue from that reviewed record, with fake coverage proving prepare is not rerun.

Before structural testing, fixed the AddMarker getter check to the installed stub's `dict[int, MarkerInfo]` key; JSON serialization uses strings only in retained captures. The fake getter now matches the documented numeric key. Existing boundary/failure cases and all R1–R3 fake guards pass; focused Ruff passes. Source pins are refreshed only after final checks.


## One-frame owned playhead-context diagnostic

R2-unlinked real first audio blade and second-position setter are retained. Subsequent Auto Select/Deselect readback preserved the complete pair SHA49dff52b40cc69ab66d11db1c62d5914bc6016a62c5ba1bd641cce2f2732f4f7 but playhead reads00:02:02:19 rather than the setter's00:02:02:20. No second blade/deletion ran. Cause is unestablished. Read-only menu lookup confirms Playback > Step One > Frame Forward exists/enabled. Added only that fixed context menu under existing guards and fake-tested its path/refusals. A bounded one-frame diagnostic requires a fresh exact pair/empty selection/playhead19, steps once, then requires the same full pair and exact20 before selection/edit may continue. No setter/blade retry.

Correction to earlier pitch wording: the raw video GetSpeed record omits PitchCorrection after unlink; it is not a literal null. Model now removes exactly that field, and retained real preparation comparison passes. The first read-only review refusal is kept; the second read-only review passes and retains its fresh full pair.
