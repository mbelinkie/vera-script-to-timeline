# Issue 149 Workflow discriminator fixture preflight

This kit is a fresh copy of the already-retained synthetic fixture set from
`out/issue149-workflow-reruns-20261002-kit-01/media/`. No protected media,
the retained Issue 141 project, or a production project was read or changed.
The source fixture bytes were copied with `cp -p`; the hashes below were
recomputed after copying.

## Core files

| file | SHA-256 | role |
| --- | --- | --- |
| `a1_alpha.wav` | `4bc4b8cfa118dab9f75ec2072f79af0c856f41566d7e2da60fca5268f7d81253` | A1 NATO words and 1000 Hz pilot |
| `a2_numbers.wav` | `d9aeccc2d50cb96d81341167450eeb1b2c43fecf0f02b9291b4cd65afa92f9ba` | A2 number words and 1500 Hz pilot |
| `a3_bed.wav` | `022e3dd779808e5b38ff870cd541d8e25fb940836443262aaa95ce8768817e2b` | A3 bed and 2000 Hz pilot |
| `base.mov` | `164348e62292c173ac23708244f6350c6a2d6211667930ebadffacc1021a7036` | source `src_id=1`, H.264 video plus embedded A1 audio |
| `cutaway.mov` | `34c364eb8debae77754448b7e272467d6fbf7a9ff46a2cca338032b778acc42e` | source `src_id=2` video control |
| `swap.mov` | `164348e62292c173ac23708244f6350c6a2d6211667930ebadffacc1021a7036` | imported W6 source copy |
| `relink_alt.mov` | `2bad2d2457c3d572d2fe3542ef22da915ec38306c8985026bec10d1289f76579` | W6 replacement: source `src_id=2` video plus A2 mono PCM |

## W6 distinct case files

The two imported source copies and two replacement copies are byte-identical
within their role but have distinct filesystem identities. This prevents the
two atomic-replacement cases from sharing a path or an accidental previous
stat result.

| path | SHA-256 | inode at fixture creation | bytes | mtime at fixture creation |
| --- | --- | ---: | ---: | ---: |
| `media/w6-cases/swapA.mov` | `164348e62292c173ac23708244f6350c6a2d6211667930ebadffacc1021a7036` | `548023099` | `3443686` | `1790976491` |
| `media/w6-cases/swapB.mov` | `164348e62292c173ac23708244f6350c6a2d6211667930ebadffacc1021a7036` | `548023104` | `3443686` | `1790976491` |
| `media/w6-cases/relink_altA.mov` | `2bad2d2457c3d572d2fe3542ef22da915ec38306c8985026bec10d1289f76579` | `548023111` | `4593112` | `1790976491` |
| `media/w6-cases/relink_altB.mov` | `2bad2d2457c3d572d2fe3542ef22da915ec38306c8985026bec10d1289f76579` | `548023119` | `4593112` | `1790976491` |

The W6 case must set the replacement file's modified time either to the
pre-swap value (kept-mtime case) or to a demonstrably new value (new-mtime
case) immediately after the atomic replacement. The original bytes and
metadata must be backed up before either case and restored exactly after both.

## Stream gate

`ffprobe` returned this stream layout for `base.mov`, `relink_alt.mov`, and all
four W6 case copies:

```text
stream 0: h264 video, yuv420p, 640x360, 25/1, time_base 1/12800,
         duration 16.000000 s, 400 frames
stream 1: pcm_s16le audio, mono, 48000 Hz, time_base 1/48000,
         duration 16.000000 s, 768000 samples
```

This is the required same-layout replacement. An audio-less replacement is
out of scope because it previously hung Resolve and would confound the W6
question.

## Intended W3 fixture geometry

Each W3 timeline is a fresh timeline in the named disposable project:

* 25 fps, 1920x1080, 48 kHz, start timecode `00:00:00:00`;
* V1/A1 linked `base.mov` over `[0,400)`;
* A2 mono `a2_numbers.wav` over `[0,400)`;
* A3 mono `a3_bed.wav` over `[0,400)`;
* A2 mapping starts with `track_mapping["1"].mute == false`.

The W3 variants differ only in the ordering of the Workflow Integration mute,
the render entry point, and the operator's intervening page/playback action.
The mapping must be restored through the Workflow Integration and its final
getter/snapshot pair must match the original, allowing only explicitly
recorded queue/page/current-context differences.
