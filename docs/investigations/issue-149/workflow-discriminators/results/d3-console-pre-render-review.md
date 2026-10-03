# D3 Console render staging gate

- **Task ID:** `/root/discriminator_output_verify`
- **Verdict:** **GO** for the bounded operator Console render.
- **Classification:** reproduced setup; no Console action or render was performed by this verifier.

The retained Workflow Integration result selected `D3-console-av-20261003` (timeline UID `dc548f02-103c-495a-8e88-c4b767aa10dc`) in project UID `0591bb41-d645-4af7-a2ee-ff75f8f43162`. Its V1/A1 items are reciprocally linked; A2 item `02572600-80b5-43ca-a7bd-6bd74f7b3a89` and A3 item `4ade3d8d-a7d6-413a-a5ae-0466ea27edf7` are independent. The shape is 1920×1080, 25 fps, 48 kHz, frames/source 0–399.

Workflow Integration changed exactly A2 `track_mapping.1.mute` from false to true. The complete pre/post pair has no other difference. The queue remains at seven jobs, rendering is false, and no Console job has been queued. External Scripting is `None`.

The Console configuration is pinned to the same project/timeline, output directory, `CustomName: D3-console-av-20261003`, and `RenderAll: true`. Its recorded source hashes are verified: Console helper `48f8d3e5499cc4073f5c25fe70dfc3a2d88a04bc459cbe5bbba3783aa6ad90bb`, harness `ef859db33d1e53136c41431a4189c053a4629d64d309b891cabffe6d9fd16438`, and config `ee05f7d1033c9b64fefaa1cc970a5cf1a9478c598075f82ebc3e89fd0011326c`. The owned paths and single-dispatch guard are valid; no replacement or protected media is involved.

The operator may now run the exact staged command once in Workspace → Console while the named timeline is current. They must leave the mapping, Fairlight controls, M/S controls, clips, and playhead unchanged and retain the generated result/progress files. This gate makes no claim about the Console render's audio output; that remains the pending observation.

Evidence: [`d3-console-pre-render-review.json`](../../../../../out/issue149-workflow-discriminators-20261003-kit-02/recovery/d3-console-pre-render-review.json), `recovery/d3-console-manual-pending.json`, and the complete mute pair under `evidence/w3-mapping-mute-d3-console-av-20261003-kit-02`.
