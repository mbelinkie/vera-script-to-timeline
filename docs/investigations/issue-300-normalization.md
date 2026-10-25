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
PCM replay and no provider transport. One authored after-word picture boundary
has supported end evidence; the other remains absent under the unchanged
acoustic quiet-gap rule. That is a real authored timing limitation requiring a
product choice. No structural provider end, next onset or frame edge is emitted
as its audible end. This repair alone does not complete #300 or unblock #275.
Private inputs, identifiers and artifact locations are excluded from this file.
