Issue 141 render **completed and restored** for job `0460d82a-3436-4efc-be12-b57c8523ebf5`. The actual status was `Complete`; the resume journal recorded **zero** `StartRendering` requests. Across the original start and resume calls, the total was one.

The MOV probe reports 9,200 video frames, 368 seconds at 25 fps, and 48 kHz 24 bit PCM audio. The helper verified its output hash. Owned job and render preset cleanup succeeded; the earlier preset remains present with its restore obligation recorded. Selection and playhead were not captured.

Full evidence: [cli-av-owned-render-resume-result.json](cli-av-owned-render-resume-result.json).