# D6-kept baseline render reference

Task ID: `/root/discriminator_output_verify`

Classification: baseline reference, not the W6 replacement result.

Resolve rendered `D6-kept-r2-20261003` through Workflow Integration with job `fa550bdf-3df3-49cc-89c6-f3a7afdc12a3`. The staged render used H.264 QuickTime, 640x360, 25 fps, 48 kHz 16-bit LPCM, full timeline, and the exact job was polled to terminal completion. Output:

`out/issue149-workflow-discriminators-20261003-kit-02/renders/d6-kept-r2/D6-kept-r2-baseline.mov`

Output SHA-256: `dbcf1eb576b12c65fa97a7b2109fc7ca160e7c472d59035d82efe46554210d9a`.

Offline analysis (`analysis-d6-kept-baseline.json`) found 399 decoded frames (the requested mark-out is 398), all source ID 1, with zero frame-code mismatches. The rendered audio had 766080 samples, A1 1000 Hz pilot `0.02828`, A2 1500 Hz pilot `0.01986`, and A3 2000 Hz pilot `0.02003`; all eight A1 NATO words and all eight A2 number words were detected. This is the unmuted reference for the later W6 restore comparison and W3 output gate.

References: the render-stage and render-poll result JSONs, their complete evidence pairs, the output file, and `out/issue149-workflow-discriminators-20261003-kit-02/analysis-d6-kept-baseline.json`.
