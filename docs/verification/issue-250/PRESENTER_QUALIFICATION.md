# Current-compiler Presenter qualification

Issue [#250](https://github.com/mbelinkie/vera-script-to-timeline/issues/250)
adds `qualification-output-current-presenter/v1`. This is a finite local
qualification profile for the retained issue-owned `presenter-alpha-01` case.
It is not a public package or creative acceptance of the temporary Presenter.

The ordinary package still refuses `TEMPORARY_PRESENTER_STILL`. The new profile
retains the compiler's single warning and replacement recovery, and labels the
result `qualification_only` / `unqualified_temporary_presenter`. Extra,
missing, changed or non-Presenter diagnostics refuse admission.

The profile authenticates the retained document and dependency bytes, then
creates a fresh execution input under the admission's `package/Execution`.
The document is byte-identical; the only dependency value refreshed is the
actual current compiler source identity (it can already match). Two actual compiler runs
must emit identical bytes. Schema validation, manifest/dependency identities,
all P5 receipts, actual original media probes, delivered media bytes and
narration proofs remain required. The host's existing sealed admission and
native authority bind that execution to its exact output and disposable target.

The Presenter must be the exact retained 320×720 RGBA PNG. Admission checks its
bytes and IHDR, decodes its actual pixels with the pinned tool, requires both
transparent and opaque pixels, and checks the emitted contain reference and
dimensions. The root continues through the Presenter interval (frames 145–280);
the independently ordered overlay spans frames 258–305. All intervals are
half-open at their compiler endpoints.

The approved #209 R16 candidate remains on its old profile and original source
pin. Its stale-compiler refusal remains valid: this change does not rewrite
its private dependency file, relax its pins, or claim the old R16 result is
current. Instead, the explicitly versioned new fixture execution above is the
current consumed input for transparent composition qualification. A source hash
alone never establishes success; admission reproduces actual compiler output
and the application check must use that admitted output.

## Validation status

All 29 initial focused issue tests pass, including admission against the retained real
preparations, ordinary-package refusal and sealed cached reopen. Earlier
package/native/controller checks also pass. Claude's read-only review completed;
its three findings were fixed: measurements load the admitted manifest, the
portable tests use a committed synthetic PNG, and cached admission verifies the
compiler envelope against the retained emitted bytes. Lint and type checks pass.

The decoded-picture helper authenticates the completed native session, source
preparations and MOV hash before measuring eight selected frames. Samples inside
the image's transparent margins must reveal the expected advancing root frames;
the opaque red/green bounds must match contain geometry, and overlay samples
must remain above the Presenter and cross its end independently. These checks
are additional to the unchanged zero-lag, unity-gain PCM residual gates.

## Actual Studio result — 2026-10-18

Resolve Studio 21.1.1 build 10 completed all seven installed stages in the fresh
saved project `VERA 250 Transparent Presenter 01`, timeline `Qualification`.
Construction, save/reopen, pre/post geometry, the owned ProRes MOV render and
fixed same-MOV PCM comparison pass. Programme residual RMS is
0.0000164077438 per channel; maximum sliding 960-sample RMS is 0.000599893700.
Limits remain 0.0004/0.006 at zero lag and unity gain.

The authenticated decoded MOV passes the transparent picture checks:

| Record frame | Visible source ordinal | Checked behavior |
| --- | --- | --- |
| 144 | root 160 | Before Presenter |
| 150 / 180 / 240 | root 166 / 197 / 260 | Root advances through transparent PNG margins |
| 270 | overlay 22 | Independent overlay is above Presenter |
| 281 / 305 | overlay 33 / 59 | Overlay continues beyond Presenter end |
| 306 | root 329 | Return reveals the continuously advancing root |

In the 480×480 decoded center crop at frame 180, the red body bounds are
`(186,67,293,412)` against expected `(187,67,293,413)`; the green head bounds
are `(214,13,265,66)` against `(213,13,267,67)`. Maximum edge error is two pixels,
within the fixed four-pixel measurement tolerance. The actual image was also
visually inspected. The initial measurement refusal included the root's green
sync flash in the green bounds; the corrected check follows the connected
Presenter component and still rejects shifted geometry. Both measurement
attempts and the original render remain retained.

The comparison and picture report bind the same native output SHA-256
`7f30c235ab488431c5cf0fa308471af4ab79bef52e9f5c19ac58ff0aeb6ad27b`.
The retained local case root is
`qualification-output-preparation/issue250-20261018-01`; the passed picture
report is `measurements/presenter-02/issue250-presenter-measurements.json`.
Only `bounded_output_residual_consistency` is claimed; creative acceptance,
internal controls, continuous stability and causal exclusivity stay unclaimed.

Studio ownership was released after completion. #249's previous project,
request and release were preserved in the normal installed-flow archives.
The #248 integration passed 191 focused checks and type/lint checks. A broad
fast run encountered seven existing target-identity clock-uncertainty refusals;
all 86 tests in that file pass on the focused rerun. The final integrated
non-slow rerun passes all 1198 tests in 177.60 seconds. TypeScript, lint and
types also pass. The current GitHub Actions gate remains required before merge.
