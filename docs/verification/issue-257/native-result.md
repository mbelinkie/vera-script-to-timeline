# Interior audio lift probe in Resolve Studio 21.1.1

The installed product probe found that `AppendToTimeline` preserves fractional
record placement but rounds source cuts for this audio source. This route does
not preserve the confirmed neighbouring words. It supplies no #215 C positive.

The test used two new saved disposable projects, an unchanged mono PCM24/48 kHz
source, the Producer's existing Audition confirmation and the separately selected
`sample-precision-release` runtime. External Scripting remained None. Native calls
entered through the installed Workflow Integration. Existing strict qualification
constructors were unchanged.

## Calibration and saved readback

The control used source frames `[0,100]` as API arguments, away from the source's
end so file clamping could not hide endpoint semantics. Resolve reported duration
`100.00000000000001`, record end `100.00000000000001`, and source end time
`4.170833333333333` seconds. The input end and record end are exclusive here.

The second target completed control save/reopen, the nonripple deletion of only
its control clip, construction of both survivors, and another save/reopen.
Readbacks were identical before and after reopening.

| Edge | Required sample | Observed sample | Difference |
|---|---:|---:|---:|
| First survivor source end | 232320 | 232232 | -88 |
| Second survivor source start | 241440 | 242242 | +802 |
| Second survivor source end | 400400 | 400400 | 0 |

The first survivor's record duration was 116 frames. The second survivor started
at record frame `120.5994005994006`, retained that fractional start, and lasted
79 frames. Its record end was `199.5994005994006`, short of the required 200.
Thus source rounding clips 88 samples from “to” and skips 802 samples from “cute.”
These are measured getter differences, not a successful PCM comparison.

## Render limitation and retained attempts

The fixed QuickTime/ProRes 422/PCM24 request was attempted on the audio-only
target. Format, single-clip mode and render-settings setters returned true;
`AddRenderJob` returned an empty string. No job was started and no MOV or decoded
PCM was produced. The reason that queueing failed is unproven; this result does
not establish a general renderer limitation. No UI rendering fallback was used.

The first target stopped after saving and closing its control clip because the
initial code incorrectly required `GetCurrentProject()` to be None. Resolve opens
a non-null automatic New Project placeholder. The fix loads the exact authorized
name and verifies project/timeline identity, matching the existing delivered
workflow. The failed target and its one-use claim were retained; the second run
used a new target and authority.

Private run records remain under
`~/Library/Application Support/VERA/sample-precision-probe/issue257-20261018-01/`:
`runs/probe-01` and `runs/probe-02`. Original media, review files, prior #215
targets and reservations were not modified. No provider, upload or sharing was
used.

After the second attempt, the existing authenticated read-only product route
reported `project.GetRenderJobList == []` for the same target UIDs. No operator
or native invocation remained running. The exact-owned cooperative lock was
released by renaming its directory into the private run root, preserving its
owner record.

## Consequence for #215

A subsequent C implementation needs a native operation that independently proves
sample-exact source edges; fractional `AppendToTimeline` arguments alone cannot
supply it. It must preserve the same original samples and neighbouring supports,
survive save/reopen, and complete a fixed native render plus PCM comparison.
Rewritten media, integer-frame enclosing cuts and looser tolerances do not meet
that requirement. A black picture control may be needed to investigate the
separate audio-only MOV queueing failure, but would not repair source rounding.

The evidence supports a negative result for this finite append route. General
Fairlight capability, hidden controls, stability and causal exclusivity remain
unverified. #215 remains incomplete.
