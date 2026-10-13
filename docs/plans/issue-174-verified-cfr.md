# #174 — verified CFR preparation

Owner: `01a12bd6-3b7d-74a3-9ce0-b1990888cef6`, `gpt-6.1-sol/high`.
Branch: `codex/issue-174-verified-cfr`; baseline
`5d59b2ad560aa18f96554b71fe34ee5b7f30dfed`.
First roadmap mutation: successful claim of #174 with this task/profile/branch.
Ready inspection: External, M, model:sol/effort:high, no previous claim;
#156/#171/#173 each Closed/Done. Retain the final reinspection receipt with evidence.

Authority: #156 plan at `e32727f0c0e65dc5a8561e0f470ed28e59bd1809`;
CN1/2/3 approved in issuecomment-6072192641; CN4 unapproved.
Product spec §§6.1–6.4, 7, 8.1–8.4, 9.1–9.6, 13; accepted plan §5.

## Scope before implementation

One Python adapter consuming occurrence source descriptors and the compiler's
exact requested range. It verifies source identity/decoded cadence/streams and
either reuses same-rate picture or publishes per-requirement CFR picture plus
synchronized PCM24/48k audio. It freezes O/P0/H, rational endpoints, explicit
handles, profile/tool identities, probes, commands and byte hashes. Attempts,
cancellation, interruption, retry and exact reuse share one atomic publication
boundary. No public frozen shape changes.

Touched surfaces: new adapter, new issue-owned tests and synthetic evidence,
this plan and operator runbook. Existing contracts/generated types, fixtures,
goldens and accepted tests remain byte-identical. No additional dependency.
Reuse repository canonical JSON/hashes and existing bounded subprocess,
staging/rename and file-lock patterns without invoking narration processing.
#156 owns policy; #171 supplies the attestation; #173 supplies pure media needs.

Exclusions: acquisition, private/original data changes, import, Research copy,
UI, scheduler/cache service, durable build composition (#157), package/Studio,
native qualification/render/upload and CN4 migration.

## Investigation and judgments

Installed FFmpeg/FFprobe: 8.1.2, Apple clang 16, Homebrew libx264 build.
The first real 16×16 numbered-luma probe showed that the proposed
`trim,setpts=PTS-STARTPTS,fps:round=up` route fails the exact selection formula
with MKV millisecond ticks, including at 24000/1001. Replacing the filter time
base with exact verified frame-index cadence (`settb=1/Fs,setpts=N`) passed
all five rates. This changes the implementation inference, not the accepted
mapping: source cadence must be verified before reconstructing its rational
filter timestamps. Never use input `-r` on an encoded source.
Primary tool reference: https://ffmpeg.org/ffmpeg-filters.html (fps/settb/atrim);
runtime measurements, rather than documentation or flags, qualify the route.

Forecast after the first probe: 3–6 remaining active hours, medium confidence;
audio delay handling and atomic recovery are the principal uncertainties.
Full validation runtime and external operator wait are separate.

Initial npm clean installation failed because the Python-only word-timing
workspace lacked its lockfile entry. Accepted #193 repaired it. The bounded
retry integrates accepted main `289cfea` (including #193/#196/#191) and passes
fresh pinned `npm ci --no-audit --no-fund`; the old temporary-install workaround
is retired. #174 adds no dependency and changes no accepted lock/control bytes.

Reassessment after initial media/recovery/refusal checks: 1–3 active hours,
medium confidence. Remaining: measured converted-pair sync matrix, retained
operator artifacts, full repository gate and required Claude CLI antagonist
review. Shared heavy-gate wait and operator review remain separate. Claude
review is required before closure/merge, against an exact implementation
commit; retain findings/dispositions and re-review substantive fixes.

## Checks and External acceptance

Test-first arithmetic/source refusals and real-tool synthetic matrix: accepted
rates, another-rate same-rate reuse, nonzero O/P0/H/inpoints, exact/short bounds,
explicit handles, rational endpoints, mono/stereo 44.1/48k AAC/PCM, start/middle/
end flash-click sync, deterministic repeat hashes, corrupt/stale/tool-policy
keys, interruption/cancellation/retry and concurrent publication.
Retain exact commands/tool/platform/profile/source/output hashes and probes.
Run focused slow tests serially, `npm run validate:fast` while iterating and
`VITEST_MAX_WORKERS=1 npm run validate` for acceptance after checking other runs.

Operator runbook will name exact synthetic artifacts and replay commands.
Expected: exact count/cadence/formula; surplus < one source frame; no sample
at/after end; PCM endpoints ≤ one 48k sample and sync residual/drift ≤1ms.
Operator reviews visible judder/quality and audible artifacts and records
result against artifact hashes. Do not invent human acceptance or close #174
while its required visible/audible External judgment is missing.

Decoded colour metadata qualifies MP4/MOV/MKV independently of missing
container stream fields; inconsistent/unknown decoded fields or conflicting
stream declarations refuse. Source-audio verification retains the original
sample rate required by the frozen compiler, while the sidecar receipt records
PCM24/48k output sample bounds. The tool identity includes adapter source bytes
as well as FFmpeg/FFprobe binaries, directly linked libraries and platform.
AAC sync probes compare only the source samples retained by the exact trim;
codec ringing removed at the boundary cannot serve as a delivered peak oracle.

## Bounded retry checkpoint

The Producer's latest “resume” continues this same task while preserving the
instruction against another blanket full suite. The r7 pipeline genuinely
exited 0 for clean install, 33 affected recovery tests, 24 installed-tool cases,
independent 98-hash/decoded-media verification, public ledger/reuse and the
fast gate (355 Python tests plus TypeScript/lint/types/generated checks).
Source/config/lock hashes match the current Claude candidate `bd1fb70`.
The remaining technical active-work estimate is 30–90 minutes, medium
confidence, after Claude returns; findings may change it. Human judgment and
an unresolved full-gate evidence blocker are separate waits, not that estimate.

Claude r3 is the required delta review of the final durability ordering fix,
corrupt-artifact refusal and public positive evidence. Do not restart a live
review or repeat unchanged passing checks. The earlier 581-test full log has
no recoverable original exit receipt and is not a qualifying pass; changed
adapter bytes independently invalidate current-source reuse. Accepted #196
does not certify this Mac media-processing boundary or subjective playback.
Retain the unmet full criterion rather than inventing an exit or overriding
the Producer's explicit execution limit. Leave #174 open until all gates pass.
