# Issue 12 Producer acceptance — EV24 Lower Third

Issue #12 stays **In review** until the Producer gives the exact acceptance
reply below. The accepted #20 library is an in-memory registration boundary;
this slice adds the pinned EV24 package and its guarded registration path. No
production Resolve library or project was changed.

## Retained automated evidence

- The packaged `EV24 Lower Third.setting` is byte-identical to the supplied
  installed setting: 210,902 bytes, SHA-256
  `7abb4e07a3c6472fd93e6b752a8623855f2fa03a8591fff10e6e33746e7ff2df`.
- The packaged `ev24_badges_atlas.png` is byte-identical to the supplied
  installed atlas: 2,305,230 bytes, SHA-256
  `008cea751e3d18a15436fe5701755c0fd7a3a023f1b7f5c585f9796007c766fd`.
- `badge_override_test_only.png` is a generated 64×64 non-production test
  image: 185 bytes, SHA-256
  `a631b15479a795f0f614b7681d9210dac74bd2583b311f8c8861682543a58003`.
  It is never offered as a production badge choice.
- `packages/contracts/src/ev24-lower-third.ts` declares the exact three-file
  package, whole-setting graph fingerprint, five trusted semantic mappings,
  supported Resolve Studio 21.1.0.0014 baseline, external font requirements,
  and 48/16/64 timing. The setting contains the Resolve `Templates:/` atlas
  reference and no machine-specific source path.
- `packages/contracts/test/ev24-lower-third.test.ts` passes 12 tests: exact
  registration and project isolation; source/control/timing evidence; typed
  `otis`, empty overrides, and project asset identity; rejection of missing,
  altered, undeclared, unlicensed, incompatible, false-provenance, absolute-path,
  wrong-graph, duplicate, and unapproved inputs without a partial revision.
- `npm run validate` passed under Node 24.19.0/npm 11.17.0: 168 TypeScript
  contract tests, 1 tooling test,
  6 progress tests, 23 roadmap tests, and 175 Python tests; lint, types, and
  generated-contract checks passed. No shared contract, fixture, golden file,
  or previously accepted test changed.

## Producer checklist

1. Open the three files in `packages/contracts/assets/ev24-lower-third/` and
   compare the setting and atlas with your supplied Resolve title files.
   **Expected:** the setting and atlas match exactly; the magenta test badge
   is recognizable as validation art and is not approved for production use.
2. Open `packages/contracts/src/ev24-lower-third.ts`, at `EV24_PROFILE`,
   `assembleEv24Package`, and `registerEv24LowerThird`.
   **Expected:** the setting is unchanged; the only VERA inputs are stable
   `country`, `year` required except for `otis`, optional top/bottom overrides, and an
   optional project-asset identity for the Badge Override Loader. Empty text
   overrides let the authored Fusion Year/Country auto-fill operate. `otis`
   never stores a Year value. The authored entrance is 48 frames, exit 16,
   minimum 64, with an elastic hold and no exposed timing controls.
3. Confirm the intended VERA destination project ID, brand approval, the
   holder and permitted project/package distribution for the setting and
   atlas, and licensed use of both **ITC Franklin Gothic LT Pro** styles
   (SemiBold ExtraCondensed and UltraCondensed). **Expected:** all declarations
   are accurate for this project; no font files are bundled. Confirm Resolve
   can use licensed copies of both faces without an Adobe API or runtime. If
   any right or font availability is uncertain, use the failure response.
4. Open `packages/contracts/test/ev24-lower-third.test.ts` and review the
   `registers one exact three-file revision only in its approved project`
   test. **Expected:** the library returns one immutable digest and one exact
   project revision; the other project sees no revision, and a duplicate
   attempt adds nothing. Confirm this matches the project availability you
   approved in step 3. The test project is synthetic; production project
   creation and Resolve installation are separate work.
5. Review the rejection cases in that test file. **Expected:** every invalid
   input returns a named failure with zero registered revisions. Review the
   source/control test to confirm the graph fingerprint and five exposed
   mappings correspond to the supplied setting, including 48/16/64 timing.

Reply on issue #12 with exactly one of:

- `ACCEPT #12 — I, <producer name>, approve EV24 Lower Third revision registration for project <project ID>, the supplied setting/atlas and test-only badge identities, brand use, asset/font rights, and package distribution. The exact project-scoped immutable revision and provenance behavior match checklist steps 1–5.`
- `FAIL #12 — checklist step <number> failed: <observed mismatch>. Required correction or decision: <what is needed>.`

Only the explicit `ACCEPT` response authorizes Done. A failure keeps the issue
In review or returns it to active work.
