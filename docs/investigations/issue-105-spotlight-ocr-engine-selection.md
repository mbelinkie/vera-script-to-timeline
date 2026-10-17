# Issue 105 — Spotlight local OCR engine evaluation and selection

Status: **Recommended for Producer acceptance**

Scope: synthetic local evaluation and #41 handoff only; no shared contract,
production capture, browser/UI, provider account, external OCR, persistence,
compiler, Resolve, or #41 implementation

Authority: GitHub issue #105; product specification Revision 2.2; accepted #40
contract commit `bd4b27d`

## Decision

Pin **Apple Vision `VNRecognizeTextRequest`, request revision 3**, using profile
`vision-r3-accurate-en-US-no-language-correction-v1`, as Spotlight's first
local OCR engine on the already established Mac local-agent host.

The initial supported execution identity is:

| Field | Pinned value |
| --- | --- |
| Provider / location | `apple-vision-local` / `local` |
| Engine/API | Apple Vision `VNRecognizeTextRequest`, request revision `3` |
| Engine release boundary | macOS `15.1`, build `24B83`, `x86_64`; Vision framework shipped with that OS |
| Model | Vision accurate text-recognition model for request revision 3 |
| Model artifact digest | Explicitly `unavailable`: Apple does not expose the embedded model artifact |
| Request settings | `.accurate`; `recognitionLanguages = ["en-US"]`; automatic language detection off; language correction off; empty custom words; no preprocessing |
| Profile | `vision-r3-accurate-en-US-no-language-correction-v1` |
| Evaluated profile digest | `sha256:c95cee13fa2e2f912ff65cb5dfeac62655cb345ccb78a7828935791baf8acd51` |
| Evaluation adapter | `vision_ocr.swift`, source digest `sha256:15613bbeab07b3905cb7b55497c53130a9dfa3cda36a255a7dd09f1f966ae6fc` |
| Evaluated executable digest | `sha256:188e152ec8cc6e9de223c71ffead1940f78e0f6964562b1c4fd5ab3869164b7c` |
| Geometry | Vision normalized lower-left coordinates to outward-rounded integer, top-left, half-open source-pixel rectangles; version `vision-normalized-to-outward-rounded-source-pixels-v1` |
| Canonical evidence | UTF-8/NFC, sorted-key integer JSON with one trailing LF; #41 must use #40's final `vera.spotlight.canonical-json.v1` rules |
| Confidence | Provider-reported line confidence; word confidence explicitly `unavailable` because Vision exposes confidence on the recognized line candidate, not on each derived word box |
| Bounds | Width/height ≤ 8192; pixels ≤ 16,777,216; encoded bytes ≤ 25 MiB; decoded bytes ≤ 64 MiB; 30 s timeout; zero automatic retries; ≤ 10,000 lines, 50,000 words, and 16 KiB UTF-8 per element |
| Privacy/cost policies | `local-device-only-no-network-v1`; `local-no-provider-charge-usd-zero-v1` |
| License/package | Proprietary Apple platform framework under the applicable Xcode/Apple SDK terms; use documented APIs on Apple-branded macOS hosts; do not redistribute the embedded model |
| Network/privacy | Local framework call only; Apple documents that Vision text-recognition processing happens on the user's device |

This is a narrow initial pin, not a claim that the opaque Apple model is stable
across operating-system updates. An unapproved platform build, request revision,
language set, correction setting, preprocessing step, adapter/canonicalization
version, or geometry rule is a different execution profile and cannot reuse the
accepted profile ID or evidence identity.

## Why Vision wins

Both candidates passed the hard local/privacy, repeatability, geometry, and
fail-closed packaging gates. Vision is selected because Spotlight first needs
complete selectable text and usable line grouping; padding can safely absorb a
loose word rectangle, while an omitted or corrupted word cannot be selected.

Across the same five synthetic 1600×900 webpage-style rasters, repeated five
times per engine:

| Measure | Apple Vision r3 accurate | Tesseract 5.5.3 OEM 1 / PSM 3 / `eng` | Judgment |
| --- | ---: | ---: | --- |
| Exact word recall | **115/124 (92.7%)** | 103/124 (83.1%) | Vision finds 12 more exact words. |
| Exact line recall | **37/40 (92.5%)** | 27/40 (67.5%) | Vision better preserves selectable page lines. |
| Mean IoU across all expected word boxes, misses = 0 | 0.668 | **0.788** | Tesseract's tighter boxes partly offset its misses. |
| Mean IoU for matched word boxes only | 0.720 | **0.949** | Tesseract is materially tighter when it finds the word. |
| Mean IoU across all expected line boxes, misses = 0 | **0.755** | 0.662 | Vision's better line recovery wins overall. |
| Mean IoU for matched line boxes only | 0.816 | **0.981** | Tesseract's surviving line boxes are tighter. |
| Identical canonical output | **5/5 fixtures, 25/25 runs** | **5/5 fixtures, 25/25 runs** | Both repeat exactly on the pinned host/profile. |
| Median wall time per invocation | 598.8 ms | **328.4 ms** | Includes process launch; #41's in-process timing may differ. |
| p95 wall time | 657.0 ms | **414.1 ms** | Tesseract is faster in this bounded run. |
| Maximum peak resident memory | 73.0 MiB | **49.3 MiB** | Tesseract is lighter in this bounded run. |

Tesseract is not selected despite its speed and box precision because its fixed
profile missed the clean page's “Open report” button, merged unrelated header,
column, and table cells into single lines, changed seven accented words in the
multilingual fixture, and corrupted the rotated phrase. Vision preserved every
word on clean, mixed-layout, multilingual, and transformed fixtures; its one
transformed-line miss was a 12-degree phrase returned as four correct word-sized
line observations.

Apple warns that accurate-mode word rectangles are guidance rather than exact
glyph segmentation. That caveat agrees with the measured lower IoU. Spotlight
uses rectangles as an author-reviewed proposal and adds explicit padding before
matte derivation; it does not treat the rectangle as automatic confirmation or
pixel-perfect character segmentation. If a future creative requirement needs
tight glyph contours rather than padded word/line regions, this selection must
be reconsidered rather than hidden inside #41.

## Corpus and scoring

All inputs are generated locally by `evaluate.py` using fictional text and
system fonts. No page was loaded or captured. The corpus digest is
`sha256:b2d8f8a05f58e9737973e4f5104e5cc36a7ebde1b413ceb63bbdfb0aab02c81a`.

| Fixture | Purpose | Vision word / line recall | Tesseract word / line recall |
| --- | --- | ---: | ---: |
| `clean-page` | Article, navigation, panel, button, footer | 100% / 100% | 92% / 62.5% |
| `mixed-layout` | Header, two cards/columns, table-like cells | 100% / 100% | 100% / 75% |
| `multilingual` | English plus French, Spanish, and German Latin text | 100% / 100% | 65% / 50% |
| `scaled-rotated` | 14 px label, 52 px banner, 12-degree phrase | 100% / 80% | 87.0% / 80% |
| `unreadable` | Tiny low-contrast and blurred text amid readable controls | 55% / 60% | 55% / 60% |

Scoring normalizes text to NFC/casefolded alphanumerics for matching but retains
the engines' exact output bytes separately. Duplicate strings are paired by the
highest rectangle intersection-over-union. A miss contributes zero to the
all-ground-truth geometry mean. The matched-only IoU therefore describes box
tightness, while recall and the all-ground-truth mean expose missing text.

The retained evidence is:

- corpus truth and raster hashes: `issue-105-spotlight-ocr-engine/fixtures/ground-truth.json`;
- complete metrics, profiles, versions, languages, timings, memory, hashes, and
  negative controls: `issue-105-spotlight-ocr-engine/benchmark-results.json`;
- canonical outputs: `issue-105-spotlight-ocr-engine/outputs/`;
- green expected / magenta observed word and line overlays:
  `issue-105-spotlight-ocr-engine/overlays/`;
- independent clean-root digest comparison:
  `issue-105-spotlight-ocr-engine/reproduction-check.json`; and
- reproducible harness and probe: `issue-105-spotlight-ocr-engine/evaluate.py`
  and `issue-105-spotlight-ocr-engine/vision_ocr.swift`.

## Language behavior

On the pinned host, Vision revision 3 reports 18 languages for `.accurate`:
Arabic (two Saudi variants), German, English, Spanish, French, Italian,
Japanese, Korean, Brazilian Portuguese, Russian, Thai, Ukrainian, Vietnamese,
Cantonese in simplified/traditional scripts, and Chinese in
simplified/traditional scripts. The selected profile nevertheless permits only
`en-US`; the multilingual fixture tests robustness of Latin text on an English
page, not approval of dynamic language switching.

Tesseract's installed Homebrew package exposes only `eng`, `osd`, and `snum`.
Additional language files exist as a separate package, but they were not
installed, evaluated, or authorized. Issue #41 must reject a declared language
outside the exact selected profile. A future language profile requires its own
corpus, profile digest, results, and Producer decision.

## Privacy, license, platform, and packaging

### Selected Apple Vision default

- The harness passes a local `CGImage` directly to `VNImageRequestHandler`.
  It passes no URL, cookie, credential, project/user identity, browser state, or
  artifact locator. It performed zero external OCR calls.
- Apple's Vision documentation states that text-recognition processing happens
  on the user's device for privacy. The model is not downloaded or bundled by
  VERA.
- Vision is proprietary Apple platform software. The applicable
  [Xcode and Apple SDKs Agreement](https://www.apple.com/legal/sla/docs/xcode.pdf)
  permits use under its terms on Apple-branded macOS systems. #41 uses only
  documented Vision APIs and does not copy, inspect, redistribute, or claim a
  license to the embedded model.
- The first supported OCR host is exactly macOS 15.1 build 24B83 on x86_64,
  matching the established Resolve/local-agent evidence host. Ubuntu CI may
  validate frozen adapter output but cannot execute this provider.
- Packaging adds no OCR executable, model file, service, account, or product
  dependency. #41 compiles the small adapter against the OS Vision framework.

### Rejected Tesseract default

- The evaluated local alternative is Tesseract 5.5.3 from the Homebrew stable
  bottle, executable digest
  `sha256:ba1ac07012b5506adec3b0231ebaeb86daac37dd1b02b46dffe00531b432af10`,
  using the installed `eng.traineddata` digest
  `sha256:7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2`.
- Tesseract and its evaluated model are Apache-2.0; its exact Homebrew formula
  lists 10 direct and 38 recursive runtime dependencies on this host. The
  [official Tesseract repository](https://github.com/tesseract-ocr/tesseract)
  and [Homebrew formula](https://formulae.brew.sh/formula/tesseract) retain the
  license/package sources.
- It is local, open source, cross-platform, faster, lighter, and more exactly
  pinnable than Apple's opaque model. Those are real strengths, but the
  evaluated text/line losses are the first unacceptable default tradeoff for a
  selectable-text Spotlight.
- It is rejected as a runtime fallback. #41 must never invoke it when Vision is
  unavailable or mismatched. Reconsideration requires a separate approved
  profile and evidence rather than opportunistic installation or fallback.

No external OCR provider is selected or authorized. Remote OCR remains disabled
under #40's explicit opt-in/privacy/cost boundary; #105 found no need to send a
captured page anywhere.

## Update policy

The selected engine is pinned by the tuple:

```text
apple-vision-local
macOS 15.1 build 24B83 x86_64
VNRecognizeTextRequest revision 3
vision-r3-accurate-en-US-no-language-correction-v1
profile sha256:c95cee13fa2e2f912ff65cb5dfeac62655cb345ccb78a7828935791baf8acd51
adapter/canonicalization/geometry version 1
```

#41 must fail closed as `engine_profile_unavailable` before raster access when
the host tuple or supported request revision does not match. The author retains
manual geometry as #40's safe fallback. A macOS update, hardware-architecture
change, Vision request revision change, language-policy change, or adapter
change requires a new profile ID/digest, a complete corpus rerun, review of all
canonical output changes, and Producer acceptance before activation. Old OCR
evidence remains bound to the old profile and is never relabeled.

## Exact adapter handoff to issue #41

Issue #41 receives an implementation decision, not permission to choose another
provider:

1. **Preflight.** Verify current project authorization, exact capture revision,
   raster artifact/digest/dimensions, whole-raster or integer half-open crop,
   the host tuple above, request revision 3 support, and the exact profile
   digest. Fail before raster access on any mismatch. No provider fallback.
2. **Request.** Decode the already authorized immutable raster locally with a
   fixed `.up` pixel orientation. Create one `VNRecognizeTextRequest` with the
   exact settings in the decision table. Pass only the raster/crop and fixed
   language setting to Vision.
3. **Raw response envelope.** Because Vision returns in-process objects rather
   than raw response bytes, serialize every returned observation in raw order
   to a versioned restricted `vision-response-envelope-v1`: exact top-candidate
   NFC text, line confidence millionths, normalized quadrilateral/box converted
   to integer source-pixel millionths, and per-word ranges/boxes. Hash and retain
   those canonical bytes as #40's raw provider-response artifact.
4. **Geometry.** Convert Vision's lower-left normalized edges outward:
   left/top with `floor`, right/bottom with `ceil`, first into source-pixel
   millionths and then through #40's integer half-open conversion. Reject the
   entire batch for non-finite, inverted, out-of-bounds, zero-area, overflowed,
   or missing line/word geometry; never omit only the bad element.
5. **Elements.** Use Vision result order as line `rawOrdinal`; enumerate NFC
   whitespace words in each recognized line and call `boundingBox(for:)` for
   exact word ranges. Derive reading order deterministically by top edge, left
   edge, then raw ordinal. Store line confidence as `provider_reported` and word
   confidence as `unavailable` with reason `vision_no_word_confidence`.
6. **Canonical evidence.** Apply #40's exact context, normalized geometry,
   evidence-seed, element-ID, canonical JSON, and final evidence-digest rules.
   Changing host, adapter, raw envelope, model/profile, geometry, or output
   creates a new attempt/batch identity.
7. **Authority.** Return only terminal attempt evidence or an immutable OCR
   batch. An empty unreadable result is a successful empty batch with no target
   proposal. The adapter cannot create author confirmation, a remap decision,
   a matte, or a build binding.
8. **Logs and retention.** Restricted artifacts may hold raster/OCR text and
   raw envelopes according to #40. Ordinary logs contain only safe IDs,
   digests, counts, bounded timing/resource values, and terminal codes—never
   pixels, text, URLs, paths, cookies, credentials, or locators.

The #41 implementation must reproduce every retained Vision canonical output
from this corpus before integration. It may replace the evaluation probe with
production code but not change the selected engine/profile or weaken #40.

## Fixture and failure matrix

| Condition | Retained evidence | Required #41 behavior |
| --- | --- | --- |
| Clean page | Vision 25/25 words and 8/8 lines; overlays show looser but complete boxes | Produce proposal evidence only; explicit author confirmation remains required. |
| Mixed layout | Vision 36/36 words and 16/16 lines; Tesseract merges independent cells/columns | Preserve provider line identities and deterministic reading order; do not infer DOM grouping. |
| Scaled text | Vision finds the 14 px label and 52 px banner | Retain exact boxes; never use font size or confidence as confirmation. |
| Rotated text | Vision finds all four words but returns four line observations | Expose valid word proposals; do not invent a joined line or silently rotate/redraw. |
| Multilingual Latin text | Vision preserves all tested accents under fixed `en-US`; Tesseract `eng` corrupts seven words | Keep default profile `en-US`; unsupported declared language fails until separately evaluated. |
| Tiny low-contrast text | Both omit the hidden phrase | Empty/missing selection stays unconfirmed; offer manual geometry. |
| Blurred text | Both omit the blurred warning | No partial guess becomes a target; offer manual geometry. |
| Confidence gap | Vision has line confidence but no provider word confidence | Store word confidence as explicitly unavailable; never synthesize or inherit line confidence. |
| Geometry gap/invalid bounds | Negative control `recognized-element-without-geometry` | Terminal `invalid_provider_geometry`; no batch, proposal, or confirmation. |
| Model/profile mismatch | Negative control uses a wrong model digest; Vision equivalent is an unapproved host/profile tuple | Fail before execution as `model_digest_mismatch` or `engine_profile_unavailable`; no fallback. |
| Engine unavailable | Negative control points at a nonexistent executable | Terminal `engine_unavailable`; no batch; manual geometry remains available. |
| Identical rerun | All 50 within-run outputs plus the independent clean-root rerun match | Same profile/input/raw output must produce byte-identical canonical evidence. |
| OCR success of any quality | Every fixture/output in this investigation | Still only an automated proposal; never silently confirm or move a Spotlight. |

## Sources and bounded limitations

- Apple's [Recognizing Text in Images](https://developer.apple.com/documentation/vision/recognizing-text-in-images)
  documents the accurate path, language configuration, normalized rectangles,
  and on-device processing.
- Apple's [`boundingBox(for:)`](https://developer.apple.com/documentation/vision/vnrecognizedtext/boundingbox%28for%3A%29)
  documents word precision for accurate mode and warns that boxes are guidance,
  not exact glyph fits.
- The [Vision framework reference](https://developer.apple.com/documentation/vision)
  documents normalized lower-left coordinates and pretrained models.
- Tesseract's [official documentation](https://github.com/tesseract-ocr/tessdoc)
  and the Homebrew formula document its Apache-2.0 local engine/package path.

This is a deliberately small synthetic corpus on one retained Intel Mac. It is
enough to choose the first bounded engine/profile for #41, not a universal OCR
quality claim. It does not prove ARM behavior, later macOS builds, arbitrary
fonts/scripts, dense tables, screenshots with photographic backgrounds, or
glyph-perfect masks. Those are blocked by the update/profile rules above, not
silently presumed.

## Acceptance traceability

| Issue #105 criterion | Evidence |
| --- | --- |
| Two local candidates; same corpus; word/line geometry, repeatability, speed/resources, languages | Comparison, corpus/scoring, language sections; retained results, outputs, overlays, reproduction check |
| Exact selected release/model/profile/package/license/platform/update/provenance | Decision, privacy/license/platform, update policy, and #41 handoff sections |
| Selected default stays local; external alternatives rejected | Privacy/package analysis and explicit remote-provider rejection |
| Unreadable, rotated/scaled, mixed, confidence/geometry, mismatch, unavailable behavior | Fixture/failure matrix and machine-readable negative controls |
| Producer accepts candidate and handoff or records first tradeoff | Checklist below; issue remains `In review` |

## Producer acceptance checklist

Review this exact artifact on the pushed issue #105 commit, then follow these
steps in order:

1. Open this report's **Why Vision wins** and **Corpus and scoring** sections,
   then open `issue-105-spotlight-ocr-engine/overlays/apple-vision/clean-page-words.png`
   and the matching Tesseract overlay.
   **Expected:** Vision finds all clean-page words including “Open report”; its
   magenta boxes are visibly looser than Tesseract's but still cover the green
   expected word regions.
2. Open both candidates' `scaled-rotated-words.png`,
   `mixed-layout-lines.png`, and `multilingual-words.png` overlays, and compare
   their canonical JSON outputs beside them.
   **Expected:** Vision preserves all words and the mixed layout; its rotated
   phrase is four correct word/line observations. Tesseract has tighter boxes
   but corrupts rotated/accented text and merges independent page regions.
3. Review `benchmark-results.json` and `reproduction-check.json`.
   **Expected:** each candidate ran five times per fixture with identical output
   digests; the independent clean-root run matches every fixture, profile,
   executable, and canonical output digest; Vision's slower 0.60-second median
   and 73.0 MiB maximum are acceptable for author-initiated local OCR.
4. Review **Privacy, license, platform, and packaging** and **Update policy**.
   **Expected:** the default sends no pixels/text outside the Mac, adds no OCR
   package or provider account, uses the documented licensed Apple framework,
   supports only the pinned macOS 15.1/24B83 x86_64 host at first, and fails
   closed until a changed OS/profile is re-evaluated and accepted.
5. Review the **Fixture and failure matrix**.
   **Expected:** unreadable/missing/invalid/mismatched/unavailable results never
   produce confirmation or a fallback provider; manual geometry remains the
   explicit safe path.
6. Review **Exact adapter handoff to issue #41**.
   **Expected:** #41 is directed to Apple Vision revision 3 and the exact
   profile/provenance/geometry/failure rules; it has no authority to pick
   Tesseract, external OCR, another language profile, or automatic confirmation.
7. Record exactly one response on issue #105:
   - acceptance: `Accepted Spotlight OCR engine selection.`
   - failure: `Issue #105 acceptance failed at checklist step <number>: <first unacceptable accuracy, privacy, licensing, or packaging result>.`

Leave issue #105 `In review` until that response is explicit. Passing checks,
this recommendation, silence, or acceptance of #40 does not close it.
