# #178 qualification readiness checkpoint

Readiness investigation only, 2026-10-13. External qualification has not
started. Owner: `01a1386b-1bc1-77d3-9390-bbc345b1c091`, gpt-6.1-sol/high,
branch `codex/issue-178-readiness`, worktree `f582`.
Baseline: `bd6048b02604954df037bf0b2dd01906e986d19d`.

## Scope and current gate

The Producer authorized investigating the exact execution route while #192
owns the sole expensive-check/native slot. This checkpoint owns only new #178
readiness, proposed change-note and operator documents. No product modules,
contracts, generated types, fixtures, goldens, accepted tests, installation,
original media, target or provider state changed. No dependency was added.
No test, lint/type, Claude, media/probe, Resolve launch or native job ran.

`roadmap inspect 178` returned OPEN, Inbox, Sol/high, M, External, no claim.
Canonical #156/#174/#177/#190 were each CLOSED and Done. The current issue's
selected #190 route supersedes its older unselected-render wording; Closed/Done
dependencies do not establish an executable qualification bootstrap.
The coordinator records the sole public readiness reservation. Promotion and
claim remain held pending route approval, ownership and actual readiness.

Authority read: the product spec §§9.1–9.4; accepted #156 §§3,5,7,8 and
CN-1/2/3 (not CN-4); accepted #189 B1/CN-189-A/B; #109 Producer acceptance;
#177's plan and public runtime; #190's delivered handoff and public proof ports;
`docs/VERIFICATION_POLICY.md`.

## Evidence-backed route findings

| Finding | Evidence at baseline | Consequence |
| --- | --- | --- |
| Existing injected delivery is genuine but v1 | Installed `VERA Delivery v1.py` and `vera-delivery-v1/release.json`; release hash `4c16bbf1731442a3da5030bb673464b0f584fba5812210cf122325a38d633eb5`; all seven declared files match their size/hash. This is the hash in [#109 Producer acceptance](https://github.com/mbelinkie/vera-script-to-timeline/issues/109#issuecomment-6117134458). No installed v2 menu/runtime was found at the plugin root. | Retain connection lineage, then build/install a separately reviewed qualification release. Existing v1 acceptance covers its two-source/two-event synthetic build, not v2 audio or fractional timing. |
| Installed app metadata matches the accepted candidate | App plist: short version `21.1.1`, bundle version `21.1.10010`; local metadata platform macOS 15.1 x86_64. | Current injected product/edition/build/suffix/interpreter and External Scripting None remain actual operator/preflight gates. Plist metadata does not prove Studio edition, a running connection or preferences. |
| Native creation is blocked before adapter construction | `workflow_v2.py:1525–1536` refuses fractional and source-audio build; factory is constructed later. `NativeProofBoundaryV2.deliver()` uses this public function. | A custom factory or a #190 success mock cannot bootstrap qualification. A public owner-approved qualification operation is needed. |
| Existing release cannot launch proof | `workflow_v2_cli.py:RUNTIME_FILES` contains v1 runtime plus `workflow_v2.py`/launcher. #190 handoff explicitly excludes proof bootstrap, discovery, control reader and receipt/probe integration. | Do not copy extra files into that inventory or run an independent script. Extend the owning release/launcher boundary with a reviewed, declared inventory. |
| Rate representation is not rational evidence | `_native_settings` calls the accepted v1 `_project_settings`, which formats a floating quotient to three decimals. #190 capture accepts the native presentation label `23.976`. | Qualification needs an explicit finite 24000/1001 → native setting-token mapping and actual output cadence measurements. Preserve rational arithmetic elsewhere; the UI label alone is insufficient. |
| Clip gain is documented, complete mixer observability is not established | Installed SDK declares `AudioVolumeEnabled`, `AudioVolume` in dB, audio pan/pitch/voice-isolation/dialogue-leveler controls, channel mapping, track enable/lock and speed getters. No complete track/bus/master effects, sends, automation, limiter and route reader was identified. #190 requires all those fields. | A reader cannot fill gaps with zeros/empty arrays. Exact documented or separately accepted control evidence must be named before capture/render; otherwise readiness fails. Applying a Fairlight preset would not prove current controls. |
| PCM renderer cannot prove final picture | #190 `render_complete_programme` sets video export false and produces stereo 24-bit/48-kHz WAV only. | Retain that acoustic port. #178 additionally needs a bounded owned picture-review render through the same audited job ownership boundary, or a separately accepted existing port; no general render service is implied. |
| The R16 package has another independent gate | `v2_package.py:555–565` requires ready preview/release with empty diagnostics/recovery actions. Accepted R16 includes temporary presenter picture; the proof lane pins both original document and dependency bytes. | Reconcile actual compiler/report/package behavior under an explicit owner note before R16 delivery. Do not patch the report, drop warnings, relabel R16 as synthetic or borrow CN192R1 as package/native approval. This inspection did not run R16 preflight or assert a specific private report's current outcome. |

The proposed remedy and ownership boundary are in
[CN-178-Q1](issue-178-native-qualification-change-note.md).
The operator delta is in
[the handoff](../verification/issue-178/operator-readiness-handoff.md).
Neither document declares a new public implementation already available.

## Reused preparation and exact pins

Reuse the complete private `parallel-178` package under the existing
`issue-145/advance-inputs` preparation root, without copying media or private
script content. Its manifest hash is
`ee139b50bbe874c3519c45d54daf4b3e7e5d5bdce78ecd5d729ccdb22b49e2b4`.
All six declared content-file hashes were independently rechecked and matched;
the result template remains unqualified and unbound. Its README, matrix,
measurement design and operator checklist provide the existing arithmetic and
24-case #174 lineage. The two overlap-preparation notes were also read.
These are preparation, not trusted authority receipts or native results.

Accepted #189 plan in worktree `b858` matched
`7fc7f361062fb35f7bf8bc1afdbc4b5cf6e72b21af27bcb873af0919560228d2`.
Current #190 public handoff file hash is
`27cd7651c0c10d1d85b21116b58e5bfc1a599f70bd776c88ae2740e59115a24e`.
Installed SDK README/stub hashes are respectively
`5f58c94da8ec3c1f390d77ad9c60675263591dc101159b302e50b5774513830b` and
`2755259ef5f57b5d477786f799892e5b86ed3945db84bf88fb69bf751b36e651`.

| Inspected source | Raw SHA-256 |
| --- | --- |
| `workflow_v2.py` | `852264025d030c09f43630a25a96a28712fc00ac480a0117c0820cb1f0a7c991` |
| `workflow_v2_cli.py` | `451bd0b3f46a121612939d2a698b431078ab940fed297c8eae556eb06ff4ff3a` |
| `workflow_v2_launcher.py` | `006d41644dd5da6f3e5be2ed89abe19dfa8715db64d9e4d8425b15516dbecb1d` |
| `roundtrip_v2_native.py` | `98ec3c098f1ab16a6b3351758de9fe8d5d3c7d5154de46c406ec9b28a534b1e4` |
| `roundtrip_v2_build.py` | `69bc8adf4ef805dbbddc0d73acb9543a8fdb87eac28749037844ea9d0f02b914` |

These are inspection pins, not the eventual installed/qualified inventory.
No #174 passing command is claimed reused yet: consumed source, command,
input/tool/profile/environment equivalence still needs comparison after the
selected route is frozen. Do not rerun unchanged 24-case media merely for a
handoff. Native targets, controls, jobs and final measurements need fresh evidence.

## Resume criteria and forecast

1. Coordinator validates CN-178-Q1 and assigns exact shared-boundary ownership;
   Producer approves the precise note before any affected owner modules or
   accepted boundaries change. Resolve complete-control and picture-port
   feasibility; settle the R16 ready-report gate separately if required.
2. Implemented/reviewed integration supplies exact public callables, declared
   release inventory, receipt/probe/control readers and reproducible handoff.
   Bind accepted source and criterion coverage; retain all production guards.
3. Reinspect live issue/claim/dependencies. Only then coordinator validates
   Ready; eventual claim belongs to this same chat, with no duplicate owner.
4. Obtain an explicit expensive-check/native grant after #192 releases it.
   No monitor, background polling or successor dispatch is added here.
5. Inspect usage separately before each new phase. Either window at >=97%
   used stops new phases after a safe checkpoint; preserve live owned work,
   notify the coordinator, and never consume a reset or change accounts.

At the initial checkpoint, remaining readiness work was estimated at 20–40
minutes active with high confidence. Conditional approved integration plus
qualification is approximately 4–10 hours active with low confidence: complete
control observability and picture-render ownership can change feasibility and
scope. Required review/full gate, heavy queue, operator installation/restarts
and human viewing/listening are separate; no queue or human-wait ETA is claimed.
Usage read at entry: 15% five-hour, 62% weekly used on the same account.

## Documentary verification

Local relative links resolve and the three documents have no trailing
whitespace. The six preparation content hashes, accepted #189 plan hash,
installed declared-source hashes and inspection pins above were read and
checked without a native/media process. The first hash utility invocation
failed because of the host's unavailable C.UTF-8 locale; the subsequent
C-locale invocation exited zero. No failed invocation is claimed successful.

Consumer inspection covered package/validation scripts, tests, generation and
the #190 source-graph inventory. Searches for these new paths in `python`,
`tests`, `packages`, `scripts`, `.github` and tool manifests returned no matches,
including a `--no-ignore-vcs` retry. #190's inventory hashes TS/schema/JSON/SVG,
Python and locks/config, not these new Markdown paths. The docs change no
executable or check input, so this readiness checkpoint uses documentary
link/whitespace/diff checks under VERIFICATION_POLICY. No existing full result
is claimed rerun or reused as new #178 acceptance, and no CI/native gate is
waived. The future implementation retains all checks in CN-178-Q1.

The checkpoint's review artifacts are ready for the coordinator's scope/owner
decision. #178 itself remains unqualified/open, without Ready promotion or
claim. New phases are held at the explicit approval and queue gates.
