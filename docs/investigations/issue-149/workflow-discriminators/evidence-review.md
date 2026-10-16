# Issue149 — Workflow Integration discriminator evidence review

Source: Claude commit `67c01157a20716a63a265ce9213afd9b4d948b02`, PR150, [summary](https://github.com/mbelinkie/vera-script-to-timeline/issues/149#issuecomment-5965294977). An independent read-only subagent compared the retained Console evidence and scripts. This review does not count as a Workflow Integration confirmation.

## Evidence-supported distinctions

W6 crossed atomic versus in-place replacement with kept versus changed file modified time. Atomic/kept rendered original source1 before and after RelinkClips(True); atomic/changed rendered original before and source2 after relink. In-place replacement failed decode before relink; only changed modified time recovered source2 after relink. Online/DateModified API values stayed unchanged. These support a bounded file-reload hypothesis for the named fixtures; the requested new WI cases must confirm it before adoption as a #141 design input.

W3 Console variants muted before any render, after baseline render, after queuing a job, from Deliver, and with Codex’s output settings. All read mute:true and rendered pilot0.00019/no number words with NATO controls retained. This narrows the conflict but does not prove entry-point causality. The script called unavailable SetRenderMode(1); the documented method used by WI is SetCurrentRenderMode(1), so exact render-mode parity was not tested. The Console render helper in the new case will use and journal the documented method and matching settings.

## Hashes reported by the independent evidence reader

| Retained content | SHA256 |
|---|---|
| [summary.json](https://github.com/mbelinkie/vera-script-to-timeline/blob/67c01157a20716a63a265ce9213afd9b4d948b02/docs/investigations/issue-149/evidence/discriminators/summary.json) | be66ddb86f305092b0744022fef166c6cd2d4f9dae511bb79090b6583b87c86b |
| [audio_def.json](https://github.com/mbelinkie/vera-script-to-timeline/blob/67c01157a20716a63a265ce9213afd9b4d948b02/docs/investigations/issue-149/evidence/discriminators/disc/audio_def.json) | f4d021e6c5cc1e203ad2e0333963843342e8765720160646bacf330165ef480d |
| [renders-sha256.json](https://github.com/mbelinkie/vera-script-to-timeline/blob/67c01157a20716a63a265ce9213afd9b4d948b02/docs/investigations/issue-149/evidence/discriminators/disc/renders-sha256.json) | 1c9be4fc14b68d16cc71d100cf524548576064ed22eaf78209cc35559685b387 |
| [d-001.json](https://github.com/mbelinkie/vera-script-to-timeline/blob/67c01157a20716a63a265ce9213afd9b4d948b02/docs/investigations/issue-149/evidence/discriminators/runner/results/d-001-setup-and-first-renders.json) | 6134763edb88e11b0171d51c591d98a87d5fdcf9afbd425e2e08f3ee9fb53832 |
| [d-002.json](https://github.com/mbelinkie/vera-script-to-timeline/blob/67c01157a20716a63a265ce9213afd9b4d948b02/docs/investigations/issue-149/evidence/discriminators/runner/results/d-002-mute-after-baseline-and-swaps.json) | 0857a7b24e10fcc3c247c5dc97bce69db30038a7d256ecd6e09ffca7d73cbc3b |
| [d-003.json](https://github.com/mbelinkie/vera-script-to-timeline/blob/67c01157a20716a63a265ce9213afd9b4d948b02/docs/investigations/issue-149/evidence/discriminators/runner/results/d-003-queue-order-page-settings-and-relink.json) | 640520999baad1a0498359ba6ed4e799a8a8b35e6512e343e1bee83e1cf35389 |

The commit retains project names and render hashes, but no timelineUIDs. These will be newly observed in the WI project. M_a/M_b/M_d/M_e used SelectAllFrames=true, 640x360, 48kHz/16bit, audio/video exports; M_e mutated on Deliver. M_f used MarkIn0/MarkOut398, 25fps, lpcm, SelectAllFrames=false. All claims remain attributable to the actual rendered outputs rather than setter success alone.

## New WI success gates

Five cases in a fresh synthetic project; External Scripting None; never access retained #141 or semi1b.mp4.

1. W6 atomic replacement, keptmtime: after RelinkClips and a completed render, decoded source1.
2. W6 atomic replacement, changedmtime: after os.utime, RelinkClips and a completed render, decoded source2. Preserve matching video/audio layout in both and restore original bytes/time afterwards.
3. W3 never-rendered timeline: WI mapping mute, readback, WI render.
4. W3 fresh timeline: WI mapping mute, then operator Console render without remapping.
5. W3 fresh timeline: WI mapping mute, then operator Fairlight page, then WI render.

Each W3 output: A2 pilot <=0.001 and no number words for silence; verify NATO/picture controls, full rendered SHA256, complete pairs and original mapping restoration. Classify failures at the actual native/harness boundary. If all three remain audible, report entry-point dependence under these tested contexts; if a Console/operator case is silent while the direct case remains audible, report evidence consistent with a deferred mix update. Neither pattern alone proves a universal internal mechanism.
