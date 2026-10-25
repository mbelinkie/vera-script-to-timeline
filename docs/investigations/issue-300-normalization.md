# Same-rate normalization clock qualification (#300)

The v2 normalizer's requested `linear=true` is insufficient: FFmpeg can use
its dynamic limiter instead. Exact replay proves the delivered PCM came from
the transform; it does not independently establish raw sample coordinates.

The additional route qualifies only the existing default v2 profile, upstream
FFmpeg 8.1.2, mono 48 kHz source, no added padding, and an **actual** second-pass
`normalization_type=linear`. The exact tool/build fingerprint remains bound to
the asset. The normalizer's graph is fixed, with no user-supplied filters:

```text
raw PCM -> same-rate format conversion -> compressor -> linear loudnorm
        -> PCM24 format conversion -> delivered WAV
```

The source basis is FFmpeg's tagged [8.1.2 compressor implementation](https://github.com/FFmpeg/FFmpeg/blob/n8.1.2/libavfilter/af_sidechaincompress.c)
(`acompressor_filter_frame` and `compressor`) and [linear loudnorm implementation](https://github.com/FFmpeg/FFmpeg/blob/n8.1.2/libavfilter/af_loudnorm.c)
(`filter_frame`, `LINEAR_MODE`). They apply gain to the current sample and
preserve frame sample order/count. [swresample](https://github.com/FFmpeg/FFmpeg/blob/n8.1.2/libswresample/swresample.c)
uses format conversion without its resampling path when rates match and no
resampling flag is requested. The compressor attack/release changes its gain
state; it does not introduce audio lookahead. Loudnorm's [documented fallback](https://ffmpeg.org/ffmpeg-filters.html#loudnorm)
is why the runtime mode must be checked.

During local replay, verbose filter negotiation must report only 48 kHz
conversions. Input/output `ashowinfo` traces must start at sample zero, be
contiguous without gaps/overlaps, preserve every source frame's coordinates,
and end at the exact source count. This trace verifies that the reviewed graph
ran with the qualified clock; timestamps alone are not proof of filter semantics.
A new FFmpeg version requires source review before adding it to this route.

Separately, the normalization identity must bind the raw audio, raw timing,
profile, normalizer version and exact tool fingerprint. The complete replayed
PCM must equal the cached PCM at identical coordinates, with equal lengths.
No offset search, trimmed prefix, inserted silence or sign-agreement shortcut
is used. Correlation is recorded as absent for this method. Its zero lag is a
consequence of the qualified graph and trace, not an assumed alignment.

Other versions/modes/profiles retain the previous independent correlation plus
exact-replay route; their ambiguity still refuses. Non-48 kHz, including Fish
44.1 kHz, retains its existing resampling/envelope path. Normalization bytes,
loudness targets, cache keys and historical caches are unchanged. Measurement
algorithm version 3 requires fresh measurement; schemas retain versions 1/2
for historical documents, while package admission requires the current version.

## Retained-input result

Both retained rows originally refused sample-correlation admission. They now
pass qualified-clock measurement and evidence verification locally, with exact
PCM replay and no provider transport. Repeating measurement produces equivalent
canonical evidence without synthesis or changing the historical caches.

The original document contains four word anchors, not five. Its original timing
map reproduces no stale anchors; native onset-only projection reproduces two:
both request after-word boundaries. The reported five stale anchors therefore
cannot be reproduced from the retained pair, and no fifth anchor is invented.
Measured evidence resolves one; the other has no supported audible end under
the unchanged acoustic quiet-gap rule. The Producer explicitly approved moving
that one picture boundary to the following word's onset in a new document
snapshot. This is an authored product decision, not a fabricated audible end.
Text, visual order and whole-row narration remain intact; the original snapshot
is preserved. No structural provider end or frame edge becomes acoustic evidence.

| Retained placement | Cause and resolution |
| --- | --- |
| Row-start picture | No word anchor; stale preparation duration refreshed normally. |
| First word anchor | Exact token/onset binding already valid. |
| Second word anchor | Missing acoustic end; Producer approved the following onset. |
| Third word anchor | Exact token/onset binding already valid. |
| Fourth word anchor | Acoustic end is supported after measurement admission. |

The remaining preparation discrepancy was an obsolete duration binding, resolved
through the ordinary local media-preparation function. All six requirements then
resolve; compilation and package verification contain eleven events with no
blocking diagnostics. Three temporary presenter-still notices remain expected.
The exact timeline rate is 24000/1001. The ordinary installed delivery route
admits that rate, while historical proof callers retain their default refusal.
Still media uses its actual source frame rate when calculating Resolve's source
duration; scaling is applied before anchor properties because changing scaling
can reset those properties in Resolve. Neutral anchor offsets are zero, matching
the existing Studio still-image observations and centered-contain contract.

Fractional delivery checks precise source times as well as record placement and
source identity. Stills must be authenticated one-frame media with a frozen
clock; narration EOF must match its hash-bound sample count and whole-row frame
extent. Video requires matching preparation/frame-map provenance, the exact
rational rate, and authored start/exclusive-end times within the existing
one-audio-sample precision rule. Only observed integer getter rounding shapes
are admitted. Integer-rate delivery retains its prior exact getter checks.
Fractional video-backed held frames with multiple decoded source frames remain
unqualified and refuse before adapter creation; this change qualifies one-frame
images and the retained narration/video mapping, not general video freezing.

The retained case passed the normal guarded release/request/bootstrap route in
Studio 21.1.1: eleven events and eleven media entries, save/reopen, source identity
and source/record placement checks, with `verified=true` and zero discrepancies.
Both narration rows remain whole. This is one untimed positive readiness check;
#275 retains ownership of the three benchmark timing cases.

Private inputs, identifiers and artifact locations are excluded from this file.
