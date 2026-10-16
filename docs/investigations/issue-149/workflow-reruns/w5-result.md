# Task ID #149 — W5 current-timeline getter result

## Challenged claim

Track getters such as `GetIsTrackEnabled("audio", index)` are current-timeline-only. With W2-X-mute current, the expected values are `[true, false, true]`; with W2-Y-solo current, they are `[true, true, true]`; reading W2-X while W2-Y is current must not be interpreted as X's state.

## Classification

**Reproduced for the bounded current/inactive context sequence.** The native result reports X current `[true,false,true]`, Y current `[true,true,true]`, and X's getter while Y is current `[false,false,false]`. The action restored X as the active timeline. This establishes the required context boundary for these getters; it does not infer operator M/S state from getters or generalize to other Resolve getters.

## Run identity and native binding

Injected Workflow Integration run: DaVinci Resolve Studio `21.1.1.10`; CPython `3.14.7`; x86_64 macOS `15.1`; External Scripting `None`. Project UID `1a05ff3a-8b04-43e3-95ab-c970b93b6415`; X timeline `W2-X-mute`, UID `abdd2270-7155-4fba-850c-82201a38f4c2`; Y timeline `W2-Y-solo`, UID `bec69cf7-c76e-4820-9e1f-9b425449614f`.

The W5 action used harness probe SHA `a19a79d684f8dbaed6d36bda0d493eed964d37888bddf7749e3bbdf601f59ab5` and launcher SHA `e4f58381c398bc0ce13130fddb25c956876f7754dc877346fe389dfb826c2450`. The Studio `21.1.1.10` and External Scripting `None` labels are dispatch/producer run metadata; the native result independently reports `status: ok` and Python `3.14.7` on macOS 15.1, and does not expose a Resolve-version getter.

## Evidence setup and preconditions

The installed primary API references were retained by hash: `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/README.md` SHA `5f58c94da8ec3c1f390d77ad9c60675263591dc101159b302e50b5774513830b`, and `DaVinciResolveScript.pyi` SHA `2755259ef5f57b5d477786f799892e5b86ed3945db84bf88fb69bf751b36e651`. Synthetic fixture manifest `media/manifest.json` is SHA `111645645106943e675418fa766fe2dfe2a2a05047d0dc8f9e9fc5e845111b39`; `base.mov` is source ID 1 (embedded `a1_alpha.wav`), and the W2 audio sources are `a2_numbers.wav` (media-pool UID `a23c9a6e-1640-4db8-b380-b16870ced30c`) and `a3_bed.wav` (UID `aa4454ba-ce62-4511-976e-e4d1ff92689d`). The owned timelines were X UID `abdd2270-7155-4fba-850c-82201a38f4c2` and Y UID `bec69cf7-c76e-4820-9e1f-9b425449614f`; their W2 item UIDs are recorded in the native snapshots.

Precondition: the project had 13 timelines, the Edit page was active, and X was current in the pre-snapshot. The API ground truth for X was Audio 1/2/3 enabled `[true,false,true]`; Y was intentionally inactive and its per-track getter fields were marked `context-only`. The bounded counterexample is the X getter read while Y was current, which returned `[false,false,false]`.

## Exact native operation order

The journal records: `GetCurrentTimeline`/`GetUniqueId` → X read (`GetTrackCount("audio")` returned `3`, then `GetIsTrackEnabled` returned `[true,false,true]`) → `SetCurrentTimeline(Y)` returned `true` → Y read returned `[true,true,true]` → X-object getter read while Y remained current returned `[false,false,false]` → `SetCurrentTimeline(X)` returned `true` → post snapshot. Post `GetCurrentTimeline`/`GetUniqueId` returned X and `GetCurrentPage` returned `edit`. This is a tested call sequence, not a claim that `SetCurrentTimeline` changes stored track state.

## Getter evidence

| context | audio 1 | audio 2 | audio 3 |
|---|---:|---:|---:|
| X current | `true` | `false` | `true` |
| Y current | `true` | `true` | `true` |
| X queried while Y current | `false` | `false` | `false` |

Action `w5-context-x-current-y-inactive-02-20261002-kit-01` returned `status: ok`; native result path is `out/issue149-workflow-reruns-20261002-kit-01/vera-issue-149-workflow-reruns-result-w5-context-x-current-y-inactive-02-20261002-kit-01.json`, result SHA `b20b95b6a1adf1f0c8e9f17e2ac55c046e5b6d52ef6674b408362392cb44def5`, and config SHA `2a2905cd2991afd45a602b0d5f90f6e14f9bffea45add03e834d9f0d278cbc0c`. Its explicit getter envelopes are `xCurrent=[true,false,true]`, `yCurrent=[true,true,true]`, and `xWhileYCurrent=[false,false,false]`; `getterContext` records X as active and Y as inactive, and the pre/post snapshots both read current timeline X (`abdd2270-7155-4fba-850c-82201a38f4c2`) on the Edit page. The immutable offline control record is `out/issue149-workflow-reruns-20261002-kit-01/w5-analysis.json`, SHA `5a217395c8378c10bce133153aa9c40d8e4cf355c8ab2ca100f19e1c7cc9a325`; `analysis-check.py` passed its fixture/control validation.

Raw W5 evidence hashes: journal `21b88000ae597f8e00842f222ced81b84064c091a8eef9b1e8a8a3aa644e9ce3`; pre/post snapshots `e9179296fb130b5dc0e036e110c1ec05953ffe3d3a20ad881800280a84ce4345` (byte-equal). The native result retains the full item/timeline snapshot and getter envelopes.

Independent checks compared the three getter envelopes against the raw native
result, confirmed the two snapshot hashes are byte-equal, and passed the
offline `analysis-check.py` control validation for
`out/issue149-workflow-reruns-20261002-kit-01/w5-analysis.json`. No full-state
equality is extrapolated beyond this captured pair.

## Context limit

The inactive read is a context miss represented by all `false` values, not evidence that W2-X was globally muted or that its stored state changed. For VERA, automation must select and verify the intended timeline before reading these controls, then restore the prior selection. No core authoring failure is demonstrated; this is a context precondition for safe automation. No render or operator-control claim belongs to W5; those are covered by the W2 export/render evidence.
