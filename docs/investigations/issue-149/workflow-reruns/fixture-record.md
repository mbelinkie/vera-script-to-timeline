# Issue 149 Phase 10 synthetic fixture record

Task #149 uses the generated kit at:

```text
out/issue149-workflow-reruns-20261002-kit-01/media/
```

The source words are the retained recorded AIFFs in
`docs/investigations/issue-149/evidence/fixtures/words/`. Their SHA-256 values
match the archived producer copies byte for byte; no new `say` recording was
made. The copied generated fixtures also match the frozen manifest
(`111645645106943e675418fa766fe2dfe2a2a05047d0dc8f9e9fc5e845111b39`). The
historical evidence fixture files were not modified.

| media file | SHA-256 | role |
| --- | --- | --- |
| `a1_alpha.wav` | `4bc4b8cfa118dab9f75ec2072f79af0c856f41566d7e2da60fca5268f7d81253` | A1 NATO words, 1000 Hz pilot |
| `a2_numbers.wav` | `d9aeccc2d50cb96d81341167450eeb1b2c43fecf0f02b9291b4cd65afa92f9ba` | A2 number words, 1500 Hz pilot |
| `a3_bed.wav` | `022e3dd779808e5b38ff870cd541d8e25fb940836443262aaa95ce8768817e2b` | A3 bed, 110 Hz bed plus 2000 Hz pilot |
| `clicks.wav` | `49fe1898a6905b8e57a84e62c1f7c920e88946d43725774bc4ce84f3b3160db6` | non-frame-aligned impulses |
| `base.mov` | `164348e62292c173ac23708244f6350c6a2d6211667930ebadffacc1021a7036` | `src_id=1`, video plus embedded A1 audio |
| `cutaway.mov` | `34c364eb8debae77754448b7e272467d6fbf7a9ff46a2cca338032b778acc42e` | `src_id=2`, video only |
| `overlay.png` | `0eaf729598941b637fe282717b6d16c39f78c0a62be84bad391d95d5b34c864d` | 50%-alpha overlay control |
| `swap.mov` | `164348e62292c173ac23708244f6350c6a2d6211667930ebadffacc1021a7036` | W6 initial copy of `base.mov` |
| `relink_alt.mov` | `2bad2d2457c3d572d2fe3542ef22da915ec38306c8985026bec10d1289f76579` | W6 replacement: cutaway video plus A2 mono PCM |
| `base_picture.mov` | `b0ef51ff62dfd7051d741620d46915836b62211467c4f46331117633ec300ebe` | W4 separate picture/audio control |
| `a1_alpha_separate.wav` | `4bc4b8cfa118dab9f75ec2072f79af0c856f41566d7e2da60fca5268f7d81253` | W4 distinct basename for separate A1 audio |

## W6 stream gate

`relink_alt.mov` was created from the staged generated-only media with the
handoff command:

```sh
ffmpeg -i cutaway.mov -i a2_numbers.wav -map 0:v -map 1:a \
  -c:v copy -c:a pcm_s16le -shortest relink_alt.mov
```

The local invocation added `-v error -y` and used absolute paths under the kit.
`ffprobe` reports the following identical stream layout for `base.mov` and
`relink_alt.mov`:

```text
stream 0: h264 video, yuv420p, 640x360, 25/1, time_base 1/12800, 16.000000 s, 400 frames
stream 1: pcm_s16le audio, mono, 48000 Hz, time_base 1/48000, 16.000000 s, 768000 samples
```

The only intended content differences are source frame code (`src_id=1` versus
`src_id=2`) and embedded audio (A1 versus A2). The archived historical
`relink_alt.mov` hash differs because this rerun mux was performed locally;
the stream gate is the acceptance condition.

## Workflow Integration input paths

The root actor should pass this generated media directory as `mediaDir` and
use only these files for the disposable project:

```text
base.mov             V1 + linked A1
a2_numbers.wav      A2 mono
a3_bed.wav          A3 mono
cutaway.mov         W6 replacement video and cutaway control
swap.mov            W6 imported item before byte swap
relink_alt.mov      W6 same-layout replacement
base_picture.mov    W4 picture-only control
a1_alpha_separate.wav  W4 separate-A1 control
```

The recorded `words/*.aiff`, `manifest.json`, and `clicks.wav` stay in the kit
for local analysis. The root actor owns Resolve imports, timeline edits,
renders, relinking, and restoration; these files are preparation-only.

## Offline analyzer

`analyze.py` reuses the retained `analyze_audio.py`, `clicks.py`, and
`decode_code.py` with explicit generated-kit paths. It emits one JSON record and
refuses paths outside the kit, so protected or historical sources cannot be
silently read:

```sh
/usr/local/bin/python3.13 docs/investigations/issue-149/workflow-reruns/analyze.py \
  --media-dir out/issue149-workflow-reruns-20261002-kit-01/media \
  --output out/issue149-workflow-reruns-20261002-kit-01/analysis.json \
  --audio W1-linked-cut=out/issue149-workflow-reruns-20261002-kit-01/renders/W1-linked-cut.mov \
  --subtitle W1-linked-cut=out/issue149-workflow-reruns-20261002-kit-01/evidence/W1-linked-cut/result.json \
  --otio W4-speed=out/issue149-workflow-reruns-20261002-kit-01/evidence/W4-speed/export.otio \
  --click W4-speed=out/issue149-workflow-reruns-20261002-kit-01/renders/W4-speed.mov@37.5 \
  --decode W6-relinked=out/issue149-workflow-reruns-20261002-kit-01/renders/W6-relinked.mov@2 \
  --control W5=out/issue149-workflow-reruns-20261002-kit-01/evidence/W5/result.json
```

`--same LABEL=PATH1,PATH2` records SHA-256 and analyzer equality for a W3
baseline/restore pair. `--control` retains Workflow Integration result JSON
including getter envelopes (`ok`, `missing`, and `error`) without interpreting
them; W5 and W7 checks remain deferred to the native evidence owner.

Run the focused semantic gate after analysis:

```sh
/usr/local/bin/python3.13 docs/investigations/issue-149/workflow-reruns/analysis-check.py \
  out/issue149-workflow-reruns-20261002-kit-01/analysis.json \
  --expect-agreement W1-linked-cut \
  --expect-scalar W4-speed=0.375 \
  --expect-clicks W4-speed \
  --expect-src-id W6-relinked=2
```

The analyzer and checker perform no Resolve, Hammerspoon, Workflow
Integration, upload, relink, or UI action.

The fixture-only structural run was verified with
`/usr/local/bin/python3.14 -S`; the resulting `analysis-structure.json` is
retained beside the kit media and passed `analysis-check.py`.
