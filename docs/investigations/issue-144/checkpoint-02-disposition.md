# Checkpoint 2 disposition

Claude reviewed `fd41725` through the existing browser and completed 17 read-only
commands. Verbatim output is `claude-checkpoint-02-verbatim.md`. Reviewer runs
are independent review evidence, not acceptance or audio calibration.

| Finding | Disposition and boundary |
| --- | --- |
| Compiler hash claims | Renamed `codeHashes` to `sourceHashes`, removed type-only generated code, and separated `lockfileSha256`. Installed packages are bound through the locked install, not fully attested. Added output byte hashes. |
| Exit code ambiguity | Persistent input/source/lock drift exits 75. New deterministic subprocess test modifies only a temporary operator file during import. Host must preflight Node version and recognize compiler refusal only from exit 1 plus a valid failure envelope. |
| Parser divergence | Entry now rejects BOM. Host will reject duplicate keys and non-finite numbers before entry invocation; standalone entry retains accepted JSON.parse duplicate-key semantics. Reformatted ordinary JSON is accepted and raw-byte bound. Generated revisions/dependencies use actual TS canonical serialization. |
| Missing coverage | Torture file-boundary outputs match frozen goldens. New output-hash, BOM and drift assertions were red (three failures) then green. 73 tests passed: 11 new plus 62 accepted compiler/validator tests; focused lint and typecheck pass. |
| Readiness cycle | Split narration-independent readiness from audio/timing readiness. Missing local original narration is an explicit future blocker. Do not silently accept #148 with missing required checks or revise #145 dependencies. Actual availability/ownership must be resolved by Producer/steward; #144 public/injected tests have no cycle. |
| Two missing core adapters | Explicit verify-only speech and local media adapters in the plan. No NarrationService/provider/Polly/boto3 construction/import. All five #35 core stages and two Studio stages run with render/delivery false. Missing bytes refuse. |
| Ripple simplification | Adopt compiler-backed geometry comparison. Qualification: fresh narration is a new source/event, unlike old split clips. Retain an explicit splice segment map and compare all retained non-narration occurrences. W1 has a real one-frame gap, so raw equality is not automatically a gapless splice proof. Unsupported composition refuses. |
| Audio calibration and labels | Independently reproduced complete per-channel reconstruction with standard library and existing ffmpeg. Unchanged picture-only render supplies gains; edited render is never fitted to pass. W1 supports are generator-declared, not independently measured speech boundaries. Measurements are not a general classifier. Freeze gate profile before verdict tests. |
| New seam tests | Added explicit reconstruction, splice, wording, linking and verify-only speech cases to plan. Tests/implementations remain outstanding except compiler tests. |
| Wording precision | ASCII space/tab/LF/CR only; sentence punctuation is covered by joining-gap refusal. Route/wording Producer decision remains pending. No omission-rebuild positive yet. |
| Revision hash and recovery | TS serializer authority only for #144-produced revisions. Intent through adapter_factory before assembly; uncertain current-folder name lookup cannot authorize retry. Require unique project-tree read-only identification or operator resolution. |

`measure-retained-w1.py` verifies published compressed/decoded hashes, full PCM
extent, exact W1 route geometry and channel separation. Report is
`retained-w1-reconstruction-measurements.json`. It preserves old media, runs no
Resolve actions, and adds no dependency. Numerical results:

- Unchanged picture-only gains: 0.999997 / 0.707942 / 0.707873 on each channel.
- Maximum 20 ms residual: picture-only 0.004246; linked-cut 0.003815.
- Disabled A1 against mandatory full routing: 0.258959.
- Synthetic half-Charlie opposite-channel overlay: 0.233422 per channel;
  averaging channels would hide it. Both channels are therefore required.
- W1 linked geometry preserves the gap [99,100) and maps [100,349) to source
  [150,399); do not silently replace it with an idealized ripple.

On October 3 the Producer reported the CLI ready. `claude auth status` confirms
authenticated Claude subscription use; CLI version 2.1.235. Future checkpoint
exchange can use the CLI directly without Producer copy/paste. Existing browser
review history remains retained. No authentication or account setting changed.
