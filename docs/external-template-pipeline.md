# External Fusion template intake, integration and review

Process update, 2026-10-16: [AGENTS.md](../AGENTS.md) and the
[verification policy](VERIFICATION_POLICY.md) govern delivery. Historical
source pins below identify product artifacts, not workflow approval gates.
Every implementation and documentation change reaches `main` through a PR.

This guide makes the accepted registration/library workflow reusable. VERA
receives externally authored animation; a package revision is immutable. A
newer revision does not change an existing use or build. The authoritative
product model is [Templates and music in the product spec](<Script-to-Timeline Product Spec - Fable Rev2.md>).
The current three-template intake set is EV24 Lower Third, EV24 Quote Box and
EV24 Table. Use the installed revisions first; a newer Table source build is
a separate candidate, not a silent replacement.

Installed intake identities observed on 2026-10-12 (SHA-256 hex below; manifest
hash values use the `sha256:` prefix):

| Candidate file | Bytes | SHA-256 |
| --- | --- | --- |
| EV24 Lower Third.setting | 210902 | `7abb4e07a3c6472fd93e6b752a8623855f2fa03a8591fff10e6e33746e7ff2df` |
| ev24_badges_atlas.png | 2305230 | `008cea751e3d18a15436fe5701755c0fd7a3a023f1b7f5c585f9796007c766fd` |
| EV24 Quote Box.setting | 36597 | `b089282e6ccab68426eb5f0b39168cb11c051e6798cbe08230b41bf640ff3754` |
| EV24 Table.setting | 194782 | `869bffd705ac949a58bcb25d6bc80de5027219792336f0d599be81162447440a` |

Lower Third/atlas match S12's accepted identities. Quote Box/Table are intake
observations, not accepted VERA revisions. Newer Table source generated hash
`1fc770b580cb205824a693dee592d7e044764b25e1d58a407fc8d2eb294cb274`;
its Fit/Shrink to Fit controls are absent from the installed candidate. The
workstation preflight is described in the [verification record](verification/issue-17/verification.md).

## Accepted sources

**S12:** [Producer acceptance of #12](https://github.com/mbelinkie/vera-script-to-timeline/issues/12#issuecomment-5770268093),
commit `59838d6a8bf7fa536af3382788a947f5701a7d2c`:
`docs/issue-12-ev24-registration-acceptance.md`,
`packages/contracts/src/ev24-lower-third.ts`, and
`packages/contracts/test/ev24-lower-third.test.ts`.
This is a historical acceptance pin; accepted implementation must also reach
`main` before it counts as delivered. Rescue PRs #228/#229 carry these foundations.

**S20:** [Producer acceptance of #20](https://github.com/mbelinkie/vera-script-to-timeline/issues/20#issuecomment-5504417300),
commit `951c658bf06fc9b06caeab88c9d43809c41cef94`:
`docs/issue-20-template-library-copy-acceptance.md`,
`packages/contracts/src/template-library.ts`, and
`packages/contracts/test/template-library.test.ts`.

Exact artifact SHA-256s are retained in [source pins](verification/issue-17/source-pins.json).
Read an artifact without merging its branch:

```sh
ctx-wire run rtk git show 59838d6a8bf7fa536af3382788a947f5701a7d2c:packages/contracts/src/ev24-lower-third.ts
ctx-wire run rtk git show 951c658bf06fc9b06caeab88c9d43809c41cef94:packages/contracts/src/template-library.ts
```

Source availability is a prerequisite, not permission to reconstruct or change
accepted artifacts.

## What exists and what still needs integration

| Boundary | Retained evidence | Limit |
| --- | --- | --- |
| Package registration, project discovery, use identity and new-project copy | S20 `TemplateLibraryService`, 15 accepted tests | In-memory, persistence-agnostic domain service; no file importer, ZIP extractor, network endpoint, durable database, UI or Resolve operation |
| First curated package | S12 `assembleEv24Package`, `registerEv24LowerThird`, `prepareEv24Values`, 12 accepted tests | Exact EV24 Lower Third package and approval path; not a generic registration profile for Quote Box/Table |
| Live placement | [#8](https://github.com/mbelinkie/vera-script-to-timeline/issues/8) | Planned integration; do not claim title insertion, track/duration verification or reopen from S12/S20 |
| Authoring form | [#9](https://github.com/mbelinkie/vera-script-to-timeline/issues/9) | Planned picker/semantic form; no current user-facing import flow is established here |
| Free delivery | [#10](https://github.com/mbelinkie/vera-script-to-timeline/issues/10) | Separate fallback work; no Free/live equivalence or baked fallback is certified by registration |
| Additional starter packages | [Inbox #99](https://github.com/mbelinkie/vera-script-to-timeline/issues/99) | Quote Box/Table need bounded profile, rights and acceptance work; installed titles alone are not registered VERA packages |

S12 names Resolve Studio `21.1.0.0014` and `fusion` as required capabilities.
That compatibility declaration and graph pin do not prove rendering on another
version, Free edition, another OS, or every resolution. Record actual edition,
version/build and tested environment for each candidate. Both required licensed
font faces must be available locally; VERA does not need an Adobe API/runtime.
Historical [curated Fusion plan](plans/curated-fusion-graphics.md) primary text,
secondary text and accent-color guidance predates S12 and is not its schema.

## Receive the package and intake brief

Before registration, retain the producer's exact supplied files privately.
Do not regenerate, convert, repair or install them as an incidental intake step.
Receive these answers with the files; facts that tooling can inspect do not
need the producer to retype them:

- Display name, stable external lineage key and source revision label; author,
  publisher, organization, source tool/version, source revision, creation date
  and attesting producer. These are S20 manifest fields.
- Intended destination project identity and approved availability. A matching
  project/template display name conveys no authorization (S20).
- Rights holder and basis for every asset, permitted project scope, embedding
  and redistribution permissions; brand approval and font-use/distribution
  evidence. Font availability is not a license declaration (S12/S20).
- Intended semantic controls/defaults, text limits, responsive rules, supported
  resolutions/rates, frame timing and minimum duration. For an unregistered
  template these remain intake statements until verified and accepted.
- Reference stills/motion and expected results, exact package format, dependency
  list, entry point and expected graph/tool identity. Record unknowns explicitly.

Retain `.setting` and any supplied `.drfx` separately with file hashes and byte
lengths. A `.drfx` is retained transport evidence, not proof of installability.
S20 accepts a decoded `ExternalTemplatePackage` with `directory` or `zip`
transport and a manifest/file byte set; it does not open an archive. S12's exact
envelope accepts `directory` only. Archive inspection, safe extraction and
`.drfx` installation need their own authorized, tested intake boundary; do not
invent a command or extension-based trust shortcut.

## Repository layout and immutable package record

The accepted S12 layout is:

```text
packages/contracts/assets/ev24-lower-third/
  EV24 Lower Third.setting
  ev24_badges_atlas.png
  badge_override_test_only.png
packages/contracts/src/ev24-lower-third.ts
packages/contracts/test/ev24-lower-third.test.ts
docs/issue-12-ev24-registration-acceptance.md
```

These paths describe the accepted commit, not guaranteed default-main files.
Future packages should follow that source/test/acceptance separation only after
rights and storage are approved; this guide does not authorize publication.
Keep restricted source, licensed fonts, logos/media and unredacted local
locators in approved private storage. Public evidence can record identities,
hashes, decisions and sanitized results without copying those bytes or paths.

S20's `PackageManifest` records schema version `external-template-package/v1`,
kind, lineage/display/revision identity, entry point, validator profile/version,
required capabilities, provenance, rights and exact files. Each file records
relative path, byte length, `sha256:` digest, media type and `rightsId`.
Do not substitute a title's display name or timestamp for an identity.

`computePackageDigest` hashes canonical manifest metadata plus its declared
file set, not just the setting's SHA-256. Rights/provenance changes can change
package identity without changing artwork. S20 derives distinct registered,
project item and project revision IDs; placed-use identity includes an exact
project revision and resolved snapshot hash. Preserve these product identities
in the immutable package/use records; no separate workflow receipt is needed.

S20 validates normalized relative POSIX paths (no traversal, absolute paths,
backslashes or case-insensitive collisions), declared/provided file agreement,
entry point, sizes/hashes, rights references, profile and compatibility. Limits
are 1,000 files and 512 MiB decoded bytes. It rejects duplicates and reports
named failures before registration state is committed. This typed service is
not a parser/security sandbox for arbitrary raw requests or Fusion code.
S12 additionally rejects machine-specific paths in package metadata and pins
its entire exact envelope/profile/provenance/approval (S12/S20).

Keep each candidate's file set isolated. Unexpected extra files and missing
dependencies are failures, not opportunities to borrow assets from another
package. The atlas remains referenced through the authored
`Templates:/Edit/Titles/Eurovision/ev24_badges_atlas.png` path; S12 does not
install or resolve that path on a target workstation.

## Register, discover and copy

Use the accepted domain API from an authorized implementation/test harness,
not a purported end-user CLI. S20's `registerPackage` requires registry
`template:intake` and `template:register`, plus project membership and
`template:manage`. `listAvailableTemplates` requires membership and project
`template:discover`; template use requires membership and `template:use`.
Retain the success digest/revision or the named failure and before/after counts.
S12's wrapper also requires explicit project, brand, distribution and font
approval, and exact rights/provenance declarations.

For new-project reuse, S20 `createProjectWithTemplates` supports:

- **None:** an explicitly empty library/report.
- **Some:** exact selected source revision IDs, preflighted together. A failed
  choice creates no project or association; it is not silently skipped.
- **All:** the current eligible exact set from selected source projects, with
  exclusions reported. Do not replace a withdrawn revision with a different one.

Destination creation and management, source discovery/copy-out capabilities,
compatibility and destination rights are checked. Cross-project copy requires
redistribution permission for every packaged file. **S12's declarations set
redistributionAllowed to false**, so its accepted registration does not grant
cross-project copy, even though S20 implements copy generally.

Copied revisions are destination-owned immutable snapshots with source evidence,
per-choice reports and a selection snapshot hash. Exact retries with a committed
idempotency key return the same logical result; changed input with that key
fails. Later source access loss or source retirement does not erase destination
snapshots or previously pinned uses. Retirement/withdrawal restricts availability
for new operations; it is not deletion or retrospective migration (S20).

## Semantic controls and responsive behavior

S12's accepted EV24 Lower Third mapping is exact:

| VERA value | Trusted target | Rule |
| --- | --- | --- |
| `country` | `ControlHub.Country` / exposed Country | Required stable identifier mapped through `EV24_COUNTRY_IDS`; reject unknown IDs |
| `year` | `ControlHub.Year` / exposed Year | Positive integer required except `otis`; `otis` omits year and rejects a supplied year |
| `topLineOverride` | `ControlHub.SongTitle` / exposed TopLine | Optional string; absent control value is empty so authored auto-fill operates |
| `bottomLineOverride` | `ControlHub.Singer` / exposed BottomLine | Same empty-override rule |
| `badgeOverrideAsset` | `BadgeOverride.Clip` / exposed BadgeOverride | Optional `asset_...` identity; never a user filesystem locator |

`otis` is the general lower-third semantic mode, not a hard-coded Fusion enum
number. S12 validates the badge identity's syntax only; actual project ownership,
asset availability, verified bytes and safe Loader resolution must be checked
by the later integration. Do not call a syntactically valid ID a verified asset.

The graph fingerprint is the whole supplied setting hash. Timing is authored
48-frame entrance, 16-frame exit, flexible hold, minimum 64 frames, with no
exposed timing controls. The old 50/30/80 direction and accent-color schema do
not replace this accepted profile. Registration records timing; it does not
prove placement duration enforcement or visual motion (S12).

Quote Box/Table controls are package-specific and need their own trusted
schemas. Do not apply country/year or lower-third timing to them. Their source
checks may exercise real Lua expressions with stand-in Text+ measurements;
that does not prove native font metrics, safe areas or rendered geometry.
Record manual fitting/overflow rules and failures explicitly; do not assume
automatic shrinking. Test the exact installed candidate, not merely a newer
builder with the same display name.

## Layered verification

The following is a reusable verification plan. S12/S20 prove the automated
domain rows only; the Resolve rows require retained real-application evidence
for each exact package/target. No new Resolve test was run for issue #17.

| Layer | Checks and expected evidence |
| --- | --- |
| Intake and identity | Exact file set, hashes/lengths, entry point, portable references, provenance/rights, approved profile and graph identity; rejection leaves no partial revision. Retain candidate manifest and sanitized result. |
| Domain automation | Valid/invalid registration, unauthorized discovery/use, project isolation, duplicate/missing/altered/undeclared inputs; None/Some/All, destination rights, atomic failure, idempotency and lifecycle retention. Reuse S12/S20 accepted test cases as patterns, not proof for a new profile. |
| Semantic automation | Exact controls/defaults, unknown-country rejection, year/otis rules, empty text overrides, asset-identity validation. For new packages test Unicode, malformed/empty data and overflow diagnostics against their own schema. Lua syntax compilation alone does not establish expression evaluation. |
| Resolve installation and Inspector | In a disposable authorized project, load the exact pinned candidate, verify title availability, graph/controls and readback. Exercise country/logo mapping, auto-fill, verified badge override and unknown-value failure; check short, long and missing text, Unicode and package-specific data. Unexpected silent substitution fails. |
| Responsive visuals | Review hold stills over representative backgrounds at every claimed resolution/aspect ratio; verify fonts, safe areas, no clipping, badge/logo alignment, text fitting, panel/table behavior and explicit overflow states. Unsupported targets remain untested/incompatible. |
| Timing and rendering | Record rate and exact frame range. Compare entrance/hold/exit at minimum and long durations; changing duration changes hold only. For Lower Third include 64 frames and a longer clip; below-minimum behavior must be tested by the duration-enforcing integration. Verify first/last frames and successful still/motion export without claiming a failed render as green. |
| Persistence and isolation | Save/reopen the disposable project; read back control values, revision/graph identity, range/track where placement is implemented, and re-render representative frames. New clips after an update use the new candidate; earlier embedded clips and projects remain unchanged. Copy/library tests do not substitute for this runtime evidence. |

For historical accepted test reproduction, use the exact source revision and
locked toolchain; on an appropriate checkout the focused commands are:

```sh
ctx-wire run rtk npm run test --workspace @vera/contracts -- test/template-library.test.ts
ctx-wire run rtk npm run test --workspace @vera/contracts -- test/ev24-lower-third.test.ts
```

Historical accepted inventories were 15 and 12 respectively; current tests may
have grown. If these files are absent from main, finish their delivery rescue
before starting a dependent feature. Old passes do not certify a new package
or runtime. Run focused checks and `npm run validate:fast` locally with the
pinned Node runtime; full `npm run validate` runs only in GitHub Actions.
Code issues get one read-only Claude CLI review; if unavailable, note that in
the PR and continue. Docs-only changes skip review. The PR diff, short test
summary and green Validate check are sufficient workflow evidence. Real
Resolve behavior still needs targeted app checks; one agent drives Resolve.

## Troubleshooting and change control

| Symptom | Evidence to collect and bounded response |
| --- | --- |
| Missing/extra/altered file, wrong digest | Compare declared and provided paths/bytes with the pinned receipt. Re-receive the original candidate; never update an accepted hash to make altered bytes pass. A changed package is a new revision. |
| Wrong graph or renamed Inspector control | Compare root/operator/input map and whole-setting hash. Stop before targeting a similar control. Producer supplies corrected package or a new profile/change decision; no agent graph rewrite. |
| Expression error or data diagnostic | Capture exact typed input, tool/input and error. Check trusted mapping and supported input range. Distinguish caller-data correction from an authored-expression repair, which requires a separately supplied revision. |
| Missing/wrong font | Compare required family/style with Resolve's actual rendered face and licensed local installation. Font files are not bundled by default. Substitution is not success; a different face/layout needs producer approval. |
| Missing atlas/logo/badge | Check declared dependency hash, portable authored reference, actual target availability and verified project asset identity. Do not substitute another project asset or arbitrary path. Capture mapping/result for the exact country. |
| Old template after update/cache | Compare installed candidate hash and the clip's embedded graph. Use a fresh disposable clip and, if needed, restart in the authorized test workflow. Do not assume reinstall updates embedded clips. |
| Registration/profile/compatibility failure | Retain named code, approved profile/version, manifest and target capabilities. Correct only inaccurate candidate metadata with provenance; do not relax the allowlist or claim version compatibility without new evidence. |
| Project discovery/copy denied | Inspect grants, membership, exact project/revision IDs and rights scope. Never infer access from names. S12's nonredistributable files need a new rights decision before cross-project copy. Retain every failed/excluded choice. |
| Rendering, duration, resolution or reopen mismatch | Record Resolve edition/build, rate, requested/observed frames and controls, logs and before/after images. Preserve the partial disposable project. Unknown runtime behavior remains pending; unit tests cannot clear it. |

Repairable intake work restores declared bytes, supplies missing factual
provenance, fixes caller values within accepted semantics, or resolves an
authorized local dependency. It never edits the supplied composition.
Brand, licensing/distribution, new controls, fitting policy, minimum timing,
Free fallback and visible supported-target behavior need producer decisions
when the product specification does not settle them. Agents decide technical
schema/compiler, generated-type, fixture, golden, dependency and test changes
and explain their effects in the PR; no approval note is needed. Correct an
unsuitable model/effort route with a brief reason and continue. Keep larger
unrelated discoveries in their own Inbox issue.

For updates, retain R1 and supply R2 as a new exact candidate with new hashes,
source revision and acceptance evidence. Compare controls, dependencies, rights,
compatibility, visuals and timing. Do not migrate existing uses/builds or
modify production projects as an incidental package update (S12/S20/spec).

## Reusable Producer acceptance handoff

Complete the technical checks above first. Ask the Producer only for actual
product/taste, rights, money, private-data or hands-on decisions. Fill the
brackets and give this short checklist for a concrete package, not this guide.

**Candidate:** `[template name / lineage / external revision]` for
`[project ID]`; package digest `[sha256:...]`, project revision `[ID]`.
**Open:** `[private preview or disposable Resolve project/timeline]` on
`[Resolve edition/build]`. Agent technical checks and the rights/provenance
summary are linked from the PR; public handoffs omit sensitive locators.

1. Open the rights/provenance summary and project availability. Confirm brand, holder,
   permitted project/distribution and licensed local fonts. **Expected:** the
   exact destination and permissions are explicit; available fonts do not
   stand in for rights. Any unresolved permission is a failure.
2. Open `[disposable Resolve project / timeline]`, select `[candidate clip]`
   and its Inspector. Perform `[enumerated control/value cases with expected
   text/logo/diagnostic per case]`. **Expected:** readback and rendered result
   match; no stale clip, substituted font, silent fallback or foreign asset.
3. Play `[minimum/long-duration timelines or previews]`.
   Compare entrance, held layout and exit at `[rates/resolutions/durations]`.
   **Expected:** approved timing and safe areas, duration changes hold only,
   readable unclipped text and explicit overflow. Judge layout, motion,
   typography, logo treatment and fitting visually; automation cannot accept
   those preferences.
4. Judge whether the visual controls/defaults, optional fields and fitting
   behavior are what you want. The agent verifies package identities,
   authorization, copy isolation and save/reopen automatically or through
   targeted app checks; the Producer need not repeat those technical tests.

Record exactly one response on the package's issue:

```text
ACCEPT #<issue> — I accept <template/revision> for project <ID>: the listed rights, visual behavior and timing are approved for the recorded target.
FAIL #<issue> — checklist step <number> failed: <observed mismatch>. Required correction or decision: <what is needed>.
```

Failure leaves that package pending. Registration acceptance does not authorize
deployment, production installation, sharing, timeline migration or other
templates. Future external and Producer gates stay binding.

## Documentation verification and remaining work

The retained [historical audit](verification/issue-17/audit.mjs) was run against
the original documentation-only baseline. Its whole-slice inventory check is
not a modern-main integration gate. For a current docs edit, check links and
whitespace; do not recreate historical inventories or hashes:

```sh
rtk ctx-wire run git diff --check
```

The [verification record](verification/issue-17/verification.md) maps all seven
#17 criteria to this guide, source pins and review. The audit checks links and
accepted artifact identity/anchors; focused source review establishes meaning.
It does not certify any template render or new registration.

Remaining intake proposals belong to existing Inbox #99: separate Quote Box
and Table profiles/rights/availability, use of the installed Table revision
versus its newer source, and retained real Resolve matrices for the exact
candidates. Refine that issue's boundaries and dependencies before promotion;
its unresolved #62 dependency is not waived here. No additional ticket is
dispatched by this guide. Live placement and authoring remain #8/#9.
