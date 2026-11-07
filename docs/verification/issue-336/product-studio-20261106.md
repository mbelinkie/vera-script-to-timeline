# #336 — actual VERA product → Studio motion/None acceptance

**2026-11-06, public synthetic sources only.** This is real **normal VERA v2
authoring input → immutable manifest/dependencies/receipt → compiler/package →
independent Mac attestation → one-use Studio import → save/reopen → rendered
and FFmpeg-decoded pixels**. It is not the earlier hand-edited phase-3 OTIO
grid alone. The retained private-local test inputs, one-use operation records,
movies and pixel JSON are in `.pipeline/336/native-live8-20261106/` (not
checked into the public repository). Every earlier failed native request was
terminal, left intact and never replayed.

## Bounded positive cases

All runs used **DaVinci Resolve Studio 21.1.1.10**, installed Mac Python
3.12.14, a verified **1600 × 900, 8-bit RGB PNG** with SHA-256
`c18809679efc20e5040d24b0bb0c29cf50f51474e5cfb4067a027c19851e096c`,
**1920 × 1080, 24 fps** authored timeline, and independently decoded
**1280 × 720, 24 fps** ProRes 422 output. This is a *source/profile-specific*
qualification: it is not evidence for arbitrary JPEGs, image codecs,
source sizes, color spaces or releases.

| Fresh product case | Guarded imported delivery | Decoded frames | Pixel result |
| --- | --- | ---: | --- |
| Linear Dynamic Zoom, cover, 24-frame occurrence | `verified`; no discrepancies; saved/reopened | 24 | 5 distinct sampled frame SHA-256s, visible moving magenta focus marker |
| Same motion rebuilt as a separate 96-frame occurrence | `verified`; no discrepancies; saved/reopened | 96 | 5 distinct sampled hashes; same duration-relative marker path |
| Explicit `None`, static contain, 48-frame occurrence | `verified`; no discrepancies; saved/reopened | 48 | All 5 sampled frames SHA-256-identical; focus marker stationary |

At relative sample fractions approximately 0, ¼, ½, ¾, final:

| Case | Frame indexes | Measured marker centers (render pixels) |
| --- | --- | --- |
| Motion 24 | `0, 6, 12, 18, 23` | `(1041,180), (1023,177), (1010,174), (993,172), (980,170)` |
| Motion 96 | `0, 24, 48, 72, 95` | `(1041,180), (1023,177), (1010,174), (993,172), (980,170)` |
| None 48 | `0, 12, 24, 36, 47` | `(959,215)` at every sample |

These are independently decoded, not inferred from a successful setter or
SDK readback. The last 96-frame sample is one frame later in relative time
than the last 24-frame sample, so the tiny final-pixel difference is expected.

The three whole-video SHA-256s are, respectively:

* 24: `8f42557ed175b53e482e76571facdf4cb721334d09c9bf18b9e4bb12ab3f8b89`
* 96: `e05d603a13d7fdc7b58ef59fba4408a86df4ec1d50c5778d142b94c0c2445ec4`
* None: `bec7ff329a0f34db40856d640dcd54afb01d8f54371b613aeaeabe99d783d0d4`

The one-use request SHA-256 identities are, respectively:

* 24: `a71b06838442643aca7948a0d6f4fabff1b7375de32046915a99639ab9e936fc`
* 96: `87bb7eabe0c8d06c068b5e6cc6906ac287d26b838d2a9afa426c02027a935539`
* None: `f0a3874991a44f4fe70c545f319d5b4e51cee531957eacc417dbb164f90a898a`

All three accepted projects were saved and closed; no prior projects or
signed package files were overwritten, and their retained source hashes
remained unchanged. All tests run in fresh nonproduction Resolve projects.

## Important safety learnings

The actual product integration initially refused for several *real*, not
mocked, issues. Each refused target and one-use request was preserved and
never replayed:

1. Relative OTIO media references resolved to the wrong original copy, or no
   source. The signed package now keeps relative references and creates a
   separately checked, non-overwriting host-local OTIO import copy with
   absolute paths to the exact hashed delivered files.
2. Resolve treated **numeric runs anywhere in a PNG basename** as image
   sequences (`[51-74]`), even with a `-still.png` suffix. New motion-bearing
   still media now use collision-free, alphabet-only UUID translation;
   older frozen package names are preserved.
3. The imported OTIO Type-22 scale enum (`2` = fit, `3` = fill) differs from
   the SDK's `resolve.SCALE_*` constants. Its verifier compares the actual
   imported OTIO enum; other SDK-based edit routes are unchanged.
4. One still image supplies exactly one **physical source frame** (`0..0`)
   even when its frozen authored **record hold** lasts 24/48/96 frames.
   Readback now checks both clocks independently, only for a proven
   one-frame native still; it does not reinterpret ordinary video trims.

## Explicitly unqualified behavior / downstream handoff

For **#164 motion/focus product policy** and **#319 web authoring**, the
reusable runtime supports *only* admitted, hash-verified, source/profile
bound native linear cover motion and explicit static None/contain. It keeps
project defaults, per-occurrence overrides, settings, bindings, source and
frame identities frozen across immutable builds. The numeric aesthetic of
presets and subject-tracking semantics remain #164's choices; the editor
integration remains #319's work.

The earlier [phase-3 native measurements](phase3-studio-results.md) prove
the same Type-59/22 raw endpoints on square/wide/portrait synthetic grids,
including actual decoded 24/48/96/144-frame motion and **one specific**
source→black-matte→motion/contain trial. Those results **do not** authorize
generic automatic derived matte creation. In this product adapter, moving
`contain` without a source-bound derived matte **refuses before native effects**;
static None/contain is positively qualified. Nonlinear easing values 1/2/3
rendered pixel-identically to linear in the synthetic grid, so requests for
nonlinear easing refuse; no silent linear substitution. Gap-exposing cover,
unmeasured focus direction/scale, reverse, other raster profiles, Free/manual
automation and custom background composition are **unsupported/not proven**
and must refuse, not fall back to a visually different request.

These refusals are real runtime limits, not claims of impossibility. This
evidence is **not** a declaration that all ordinary images automatically
receive the full adopted motion treatment. A broader source normalization
and provenance-preserving matte process need separate source-bound positive
qualification before any such promise can be implemented.
