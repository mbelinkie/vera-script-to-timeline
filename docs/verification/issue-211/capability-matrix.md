# #211 — immutable actual capability matrix

Sanitized exact extraction of all 71 `gaps` entries from capability report
`2d1141bda6942baa0f83da2cb49f0f104801ce2ea853bccee5aab37d24dc4943`.
Counts: 5 supported, 23 ambiguous, 43 unsupported. Empty clip/job inventories
are unexercised observations; unsupported readers remain unavailable.

| Required field | Actual status | Actual reason |
| --- | --- | --- |
| clip.enabled | ambiguous | getter visibility only; effective route/mix remains unproven |
| clip.mute | unsupported | no complete documented control reader |
| clip.solo | unsupported | no complete documented control reader |
| clip.gainDb | ambiguous | getter visibility only; effective route/mix remains unproven |
| clip.pan | ambiguous | getter visibility only; effective route/mix remains unproven |
| clip.effects | ambiguous | item properties expose selected effects only; not all effects |
| clip.sends | unsupported | no complete documented control reader |
| clip.automation | unsupported | no complete documented control reader |
| clip.destination | unsupported | no complete documented control reader |
| clip.channelMap | ambiguous | getter visibility only; effective route/mix remains unproven |
| track.enabled | supported | track-enable getter visibility; full mixer controls unproven |
| track.mute | unsupported | no complete documented control reader |
| track.solo | unsupported | no complete documented control reader |
| track.gainDb | unsupported | no complete documented control reader |
| track.pan | unsupported | no complete documented control reader |
| track.effects | unsupported | no complete documented control reader |
| track.sends | unsupported | no complete documented control reader |
| track.automation | unsupported | no complete documented control reader |
| track.destination | unsupported | no complete documented control reader |
| track.channelMap | unsupported | no complete documented control reader |
| bus.enabled | unsupported | no complete documented control reader |
| bus.mute | unsupported | no complete documented control reader |
| bus.solo | unsupported | no complete documented control reader |
| bus.gainDb | unsupported | no complete documented control reader |
| bus.pan | unsupported | no complete documented control reader |
| bus.effects | unsupported | no complete documented control reader |
| bus.sends | unsupported | no complete documented control reader |
| bus.automation | unsupported | no complete documented control reader |
| bus.destination | unsupported | no complete documented control reader |
| bus.channelMap | unsupported | no complete documented control reader |
| master.enabled | unsupported | no complete documented control reader |
| master.mute | unsupported | no complete documented control reader |
| master.solo | unsupported | no complete documented control reader |
| master.gainDb | unsupported | no complete documented control reader |
| master.pan | unsupported | no complete documented control reader |
| master.effects | unsupported | no complete documented control reader |
| master.sends | unsupported | no complete documented control reader |
| master.automation | unsupported | no complete documented control reader |
| master.destination | unsupported | no complete documented control reader |
| master.channelMap | unsupported | no complete documented control reader |
| master.limiter | unsupported | no documented current master limiter getter |
| programme.gainDb | unsupported | no complete documented programme control reader |
| programme.effects | unsupported | no complete documented programme control reader |
| programme.limiter | unsupported | no complete documented programme control reader |
| programme.automation | unsupported | no complete documented programme control reader |
| programme.destination | unsupported | no complete documented programme control reader |
| render.queue.AudioCodec | ambiguous | existing job visibility; no candidate configured/exercised |
| render.queue.AudioBitDepth | ambiguous | existing job visibility; no candidate configured/exercised |
| render.queue.AudioSampleRate | ambiguous | existing job visibility; no candidate configured/exercised |
| render.queue.FrameRate | ambiguous | existing job visibility; no candidate configured/exercised |
| render.queue.FormatWidth | ambiguous | existing job visibility; no candidate configured/exercised |
| render.queue.FormatHeight | ambiguous | existing job visibility; no candidate configured/exercised |
| render.queue.MarkIn | ambiguous | existing job visibility; no candidate configured/exercised |
| render.queue.MarkOut | ambiguous | existing job visibility; no candidate configured/exercised |
| render.queue.RenderMode | ambiguous | existing job visibility; no candidate configured/exercised |
| render.queue.OutputFilename | ambiguous | existing job visibility; no candidate configured/exercised |
| render.queue.ReplaceExistingFilesInPlace | ambiguous | existing job visibility; no candidate configured/exercised |
| render.queue.IsExportVideo | ambiguous | existing job visibility; no candidate configured/exercised |
| render.queue.IsExportAudio | ambiguous | existing job visibility; no candidate configured/exercised |
| render.queue.JobId | ambiguous | existing job visibility; no candidate configured/exercised |
| render.queue.TimelineName | ambiguous | existing job visibility; no candidate configured/exercised |
| render.queue.TargetDir | ambiguous | existing job visibility; no candidate configured/exercised |
| render.candidates.GetRenderFormats | supported | enumeration only; PCM/picture settings/output unqualified |
| render.candidates.GetAudioRenderFormats | supported | enumeration only; PCM/picture settings/output unqualified |
| render.candidates.GetRenderCodecs | ambiguous | enumeration only; PCM/picture settings/output unqualified |
| render.candidates.GetAudioRenderCodecs | supported | enumeration only; PCM/picture settings/output unqualified |
| render.candidates.GetRenderResolutions | ambiguous | enumeration only; PCM/picture settings/output unqualified |
| render.candidates.GetCurrentRenderFormatAndCodec | supported | enumeration only; PCM/picture settings/output unqualified |
| render.actualOutputCadence | unsupported | no job or output produced by read-only preflight |
| render.actualPCMProfile | unsupported | no job or output produced by read-only preflight |
| render.actualPictureQuality | unsupported | no job or output produced by read-only preflight |

## Candidate evidence (enumeration only)

- `format:mov.GetRenderCodecs`: Apple ProRes 422 → `ProRes422`.
- `codec:mov:ProRes422.GetRenderResolutions`: includes 1920×1080.
- `format:mov.GetAudioRenderCodecs`: Linear PCM → `lpcm`.
- `format:wav.GetAudioRenderCodecs`: Linear PCM → `lpcm`.
- `project.GetCurrentRenderFormatAndCodec`: `format=unknown`, codec empty.

No actual setter, queued candidate job, picture/PCM output or complete-control
consumer was exercised by this report. These selections remain proposed.
