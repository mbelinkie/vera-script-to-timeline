# Issue 110 — injected Resolve Fairlight capability boundary

## Outcome

On Resolve Studio 21.1.0 build 14, the injected Python 3.14 boundary supports direct channel mapping, Voice Isolation, and Dialogue Leveler with real mutation/readback evidence. Loudness normalization and the requested 48 kHz Linear-PCM WAV render path failed closed and are `unavailable` on this installed build. EQ/dynamics/preset application remains `operator-only` because no named preset was authorized and the public API cannot read back and safely restore the relevant state.

## External evidence

The operator launched **Workspace > Workflow Integrations > VERA Issue 110 Fairlight Probe** on 2026-09-10 with the installed config recording **External scripting using: None**. Resolve injected CPython 3.14.7 and reported DaVinci Resolve Studio 21.1.0 build 14. The fresh project was `VERA Issue 110 Fairlight Probe 20260910-000458`.

The probe generated only a one-second, 48 kHz, 16-bit stereo WAV: a 440 Hz sine on channel 1 and an 880 Hz sine on channel 2. Its SHA-256 remained `afd63294ad25c13faec39066d4d858338397a1f70b1286b155a468f45c267239`. No presenter media path or production project is present in the code, config, or retained report.

| Capability | Status | Retained evidence |
| --- | --- | --- |
| Channel mapping | `supported-api` | `SetAudioMapping` changed one stereo mapping using channels 1+2 to one mono mapping using channel 1 only; `GetAudioMapping` returned the requested mapping. |
| Voice Isolation | `supported-api` | Disabled/amount 0 changed to enabled/amount 37, read back exactly, then restored to disabled/zero. |
| Dialogue Leveler | `supported-api` | Enable, mode, loud/soft treatment, background reduction, and output gain changed together, read back exactly, then restored to the prior values. |
| Loudness normalization | `unavailable` | `Timeline.NormalizeAudioLevel` returned false. No gain change was claimed, and the clean original remained enabled. |
| EQ/dynamics/preset | `operator-only` | No exact preset was authorized. The installed public API can enumerate/apply Fairlight presets but cannot read the current preset or EQ/dynamics state and safely restore it. |
| 48 kHz PCM-WAV render | `unavailable` | Discovery selected `wav`/`lpcm` with 48 kHz, 24-bit audio-only settings, but `SetCurrentRenderFormatAndCodec` returned false. No render job or replacement attachment was claimed. |

The unavailable render path saved, closed, and reopened the project with the original item enabled and no replacement item. The final source hash matched, the original timeline item remained present, and the report contained no discrepancy. This is the issue's permitted explicit failed-closed result for attachment/replacement/removal rather than a claim based on method enumeration.

The structured report retains official Blackmagic Design support, Fairlight, and Fairlight Audio Guide URLs with a 2026-09-10 retrieval date. It also hashes the installed `README.md` (`5f58c94da8ec3c1f390d77ad9c60675263591dc101159b302e50b5774513830b`) and `DaVinciResolveScript.pyi` (`00078fa1256851b9807621a4eea5e670f4266b0e7003763cba4a62655543f0ec`).

## Earlier failed attempt

The first disposable project, `VERA Issue 110 Fairlight Probe 20260909-235218`, stopped before media import because the probe passed the image-sequence dictionary form to `ImportMedia`. The retained failure proves that the synthetic source hash was unchanged and no original or replacement timeline item existed. The adapter was corrected to use Resolve's ordinary list-of-paths form; no failed project was reused or deleted.

The successful run generated one stale handoff sentence that assumed a rendered WAV existed. The report itself correctly records `pcmWavRender: unavailable` and no attachment. The handoff generator and retained handoff were corrected after the run; no additional Resolve project was created solely to refresh derived prose.

## Boundary for #108

#108 may automate only the `supported-api` operations with exact version matching and retained mutation/readback/restoration. It must perform EQ/dynamics/preset work as an operator step, refuse normalization and PCM-WAV replacement on this build, preserve clean presenter audio, and collect UI/final-state evidence before comparing any treatment. This investigation makes no #108 treatment or presenter-sample decision.

## External acceptance

After the successful run, the operator confirmed that External Scripting remained `None`; channel 1 mapped to one mono track with channel 2 excluded; the original clip was enabled with an empty replacement track and restored Voice Isolation/Dialogue Leveler state; and no existing project or presenter media was touched. The exact confirmation is retained in `docs/verification/issue-110/external-acceptance.md`.
