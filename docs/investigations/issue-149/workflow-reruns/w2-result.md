# Task ID #149 — W2 mute/solo render result

## Challenged claim

Manual Edit-page M/S controls produce the intended rendered program: W2-X with
Audio 2 muted contains NATO words only, while W2-Y with Audio 2 soloed contains
the number words only. API track getters are not used as a substitute for the
operator control state; the accompanying OTIO exports are the machine-readable
control evidence.

## Classification

**All required Phase 10 W2 gates pass.** X with Audio 2 muted exports the
expected disabled control and renders with no number words; Y with Audio 2
soloed exports the expected `SoloOn:true` control and renders with the number
words only. After the producer turned both controls off, the required Y
`SoloOn:false` export and neutral render were independently analyzed: all 16
words and baseline PCM returned. The optional neutral-X extension was stopped
by a later read-only context guard after unrelated timecode/Out-mark drift; it
is explicitly unrun and is not presented as a Phase 10 failure.

## Run identity and native binding

Injected Workflow Integration run: dispatch metadata identifies DaVinci Resolve
Studio `21.1.1.10` with External Scripting `None`; CPython `3.14.7`; x86_64
macOS `15.1`; project UID
`1a05ff3a-8b04-43e3-95ab-c970b93b6415`. Frozen probe SHA
`a19a79d684f8dbaed6d36bda0d493eed964d37888bddf7749e3bbdf601f59ab5`; launcher
SHA `e4f58381c398bc0ce13130fddb25c956876f7754dc877346fe389dfb826c2450`.
The producer attested `both set` in action
`observe-operator-both-set-02-20261002-kit-01`; its result SHA is
`26815a66bb8f31bb24295c1fa8f5eccda1f010a111fb15d332d6bbf954817d2f`.

The installed API references were retained by hash: `README.md` at
`/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/README.md`
SHA `5f58c94da8ec3c1f390d77ad9c60675263591dc101159b302e50b5774513830b`,
and `DaVinciResolveScript.pyi` SHA
`2755259ef5f57b5d477786f799892e5b86ed3945db84bf88fb69bf751b36e651`.
The generated fixture manifest is
`media/manifest.json`, SHA
`111645645106943e675418fa766fe2dfe2a2a05047d0dc8f9e9fc5e845111b39`.

The exact target identities were retained in the export snapshots. Timeline X
(`W2-X-mute`, `abdd2270-7155-4fba-850c-82201a38f4c2`) contains V1 item
`4a88fdc6-7b55-4ef1-9c9e-546be4f5332f`, A1 item
`9c9ef57a-af88-4943-a00b-f57cec77fa26`, A2 target item
`3e165f42-b6dc-46c0-8a85-9e11d8291045`, and A3 item
`f6ca11b7-3c9b-46c0-8a85-9e11d8291045`; its V1/A1 MediaPoolItem source is
`a25cfcec-f490-4151-a608-6088dae3c5ec`, A2 source is
`a23c9a6e-1640-4db8-b380-b16870ced30c`, and A3 source is
`aa4454ba-ce62-4511-976e-e4d1ff92689d`. Timeline Y
(`W2-Y-solo`, `bec69cf7-c76e-4820-9e1f-9b425449614f`) contains V1 item
`973c0309-6a87-4bc2-8e06-9540eb891c66`, A1 item
`85186c7f-a9d4-4b2c-8a60-399032dfae1e`, A2 target item
`03557932-18df-4fcd-b87a-08d3dee2460d`, and A3 item
`c030a496-c292-4ab8-8953-052f0ba9b5e1`; it uses the same three source UIDs
(`a25cfcec-f490-4151-a608-6088dae3c5ec`,
`a23c9a6e-1640-4db8-b380-b16870ced30c`, and
`aa4454ba-ce62-4511-976e-e4d1ff92689d`).

## Control and render evidence

| Case | Timeline UID | OTIO control result | Render/poll | Media SHA |
|---|---|---|---|---|
| W2-X-mute-02 | `abdd2270-7155-4fba-850c-82201a38f4c2` | Audio 2 `enabled:false`, `SoloOn:false`; Audio 1/3 enabled and unsoloed. OTIO SHA `1fade39d42686a7363dcc079355aa058fc5fb7d166a9822fc05057da1e941fc2` | job `b3553291-9b94-4c92-8c08-9a3e7ffef619`; poll terminal `Complete` 100%; native poll result SHA `7b1086e4d628f0574390045fe5f552a0a1357f0067fb9b7187098ab7414c5f8c` | `ad90cf9be99b3617fcbdef8ea2908b292f72cbf37f126950fafbab9c80ad684f` |
| W2-Y-solo-02 | `bec69cf7-c76e-4820-9e1f-9b425449614f` | Audio 2 `enabled:true`, `SoloOn:true`; all tracks enabled, Audio 1/3 unsoloed. OTIO SHA `0cf898d0d673a21ea4118fb0f9f646b0f071344ca9a3b26b1a017824889bce7e` | job `a24aeac0-f539-4798-ae9b-00c9baedd86d`; poll terminal `Complete` 100%; native poll result SHA `4cfa83afe3e8deeb1643ff5133f868a8194ce16b14a6313dff757581b8dec269` | `a7469cbe9224e33d95d8f52f5da328dbe892c13c2321fdf00c53a6c3badf472d` |

Both renders are H.264 640×360, 25 fps, 399 frames, 15.96 s, signed 16-bit
PCM at 48 kHz. The export action results are X SHA
`7fbe158f45c7289d664085645908f5a0dc0a36240989251e1dbc34f44ab5645c` and Y SHA
`9bd3bc5c4a7791f8774909c54c5e9b275a52e3049155367b10513a33ea294e51`.

## Measured output gates

The retained analyzer is `out/issue149-workflow-reruns-20261002-kit-01/w2-analysis.json`,
SHA `3873c23a33f2a6c8270540d9a154e469c8532c80f00a041b32fe9763725d1994`;
`analysis-check.py` passed the focused W2 gate.

- **X mute:** NATO `alpha`–`hotel` present at scores 0.995–0.997; number
  words absent under the analyzer presence threshold; pilot `1500=0.00019`
  (≤0.001). Decode: 399 frames, source ID 1, zero frame mismatches.
- **Y solo:** number words `one`–`eight` present at score 1.0; NATO words
  absent under the analyzer presence threshold; pilots `1000=0.00043` and
  `2000=0.00013` (both ≤0.001). Decode: 399 frames, source ID 1, zero frame
  mismatches.

The OTIO and render outputs support the bounded on-state interpretation. The
earlier W5 current/inactive getter sequence is documented separately; no W2
conclusion is inferred from getters alone.

## Raw evidence bindings and limit

X export evidence: journal SHA
`1fcd2d02399487faaf719363af900efff635bb5f2d612cfe7b30b0b8ca9a96a3`; pre/post
snapshot SHA `e9179296fb130b5dc0e036e110c1ec05953ffe3d3a20ad881800280a84ce4345`.
Y export evidence: journal SHA
`0c8832fcface519d3c6697c9b4a9eb4a1f1d24a99e3c2ce3f1388594a9a1642c`; pre/post
snapshot SHA `a3c21b5642daa9cb34ccef3fd9536a63b3500d4139762f76cdaf737acdc30b5d`.

## Native order, returns, and complete raw pairs

The required order was: producer attestation → X timeline selection → X OTIO
export → X render stage → X terminal poll; the producer’s Y selection was
already current → Y OTIO export → Y render stage → Y terminal poll; producer
restoration attestation → Y Solo-off OTIO export → Y neutral render stage → Y
terminal poll → owned context restoration → one final SaveProject checkpoint.
The X selection returned `SetCurrentTimeline=True` and page readback `edit`;
each OTIO export returned `True`; each render stage set H.264/MOV and mode 1,
returned `True` for the settings/readbacks and `StartRendering`, and queued
exactly one job with `MarkIn=0`, `MarkOut=398`, 640×360, 25 fps, lpcm 48 kHz,
16-bit stereo. Each terminal poll returned `Complete` at 100%. The final
checkpoint called `SaveProject()` once and returned `True`.

Every native action retained a complete `pre.json`/`post.json` pair and
`journal.jsonl` under the generated kit. The exact pair bindings and result
hashes are:

| action | result SHA | journal SHA | pre SHA | post SHA |
|---|---|---|---|---|
| `select-timeline-w2-x-mute-02` | `1b8ee763799c129068cab853c365d6c1185004d18b3bbe05b23504bce7742ca2` | `0b54d43282d084782858cc9d7fdf5a118b91e9610936b6649cc48a3d4be15323` | `72572410521d47ccfc9ce94d3d86a9388c4ff6905770bfd54b53e4a4c8e294c2` | `e9179296fb130b5dc0e036e110c1ec05953ffe3d3a20ad881800280a84ce4345` |
| `w2-export-x-mute-02` | `22589c648863a5aba582832ffa52dfa8814f1610efb8f4682926c8b0a5c9df6e` | `1fcd2d02399487faaf719363af900efff635bb5f2d612cfe7b30b0b8ca9a96a3` | `e9179296fb130b5dc0e036e110c1ec05953ffe3d3a20ad881800280a84ce4345` | `e9179296fb130b5dc0e036e110c1ec05953ffe3d3a20ad881800280a84ce4345` |
| `render-stage-w2-x-mute-02` | `e0b7a156ee9e4dae6012da01430e7f8add97e39e9503bfe0e2a0f668a4551a01` | `a62911053b94be8f93782c81df62497eea0886fdf8b2bf9f233cdabb5a9288b9` | `e9179296fb130b5dc0e036e110c1ec05953ffe3d3a20ad881800280a84ce4345` | `9ff768510811e9fadf623afb2fc9a94f82113adc9091f2b6c15c9fda9895f1e7` |
| `render-poll-w2-x-mute-02` | `7b1086e4d628f0574390045fe5f552a0a1357f0067fb9b7187098ab7414c5f8c` | `4efa8c5b775598eab76ecf2e58228cf693fb078a206e7854953c036bd1a1667f` | `1b69b5e6d3b710243c52b4a50211eb8ad10adf6e39af0a3120e49d6907a65d03` | `1b69b5e6d3b710243c52b4a50211eb8ad10adf6e39af0a3120e49d6907a65d03` |
| `w2-export-y-solo-02` | `4a92bca6c6a3a16d7818af2eb0bdc8f7374d52f7d9fd0952e2069447ade8b332` | `0c8832fcface519d3c6697c9b4a9eb4a1f1d24a99e3c2ce3f1388594a9a1642c` | `a3c21b5642daa9cb34ccef3fd9536a63b3500d4139762f76cdaf737acdc30b5d` | `a3c21b5642daa9cb34ccef3fd9536a63b3500d4139762f76cdaf737acdc30b5d` |
| `render-stage-w2-y-solo-02` | `df6fc14c61b22e52b73a084e0e69a23f99197fd78c79fc0f5c9275dd5daf667e` | `fb417843c2794e20a20d4ee1c9fe1c830c98cbc52dbd7696bbbc208a7c3c65b2` | `a3c21b5642daa9cb34ccef3fd9536a63b3500d4139762f76cdaf737acdc30b5d` | `eb1fafe317ac2813e89e132c38f16d6418c1eb6ceb44763472d8e0e20fef1b07` |
| `render-poll-w2-y-solo-02` | `4cfa83afe3e8deeb1643ff5133f868a8194ce16b14a6313dff757581b8dec269` | `cf94e583a799d4afc6f993af8031c0ed4216593a86b063b4be508f98db9480c5` | `72572410521d47ccfc9ce94d3d86a9388c4ff6905770bfd54b53e4a4c8e294c2` | `72572410521d47ccfc9ce94d3d86a9388c4ff6905770bfd54b53e4a4c8e294c2` |
| `observe-operator-restored-01` | `694ffa95cc9e223d4400a2e37e1f9c5347ac1816415de6952902007795b65ca0` | `4aed097ba5b1fed68feaa8a68fd10f25ef12ac10cdfdb625d16e9c7fb040f81a` | `d8f9994924215770644224b1d89c866ae8fb044be7e94632bef76502623962c6` | `d8f9994924215770644224b1d89c866ae8fb044be7e94632bef76502623962c6` |
| `w2-export-y-solo-off-restored-02` | `dda0e70bdfe964a24904cb272b476f9765371d1d7ac2a4b052a693267dc44df5` | `af3dbeb1b7ffa690594a7d9a0d6d5bb9d90cd5884580d8f6b2a25b7b35e38ae6` | `d8f9994924215770644224b1d89c866ae8fb044be7e94632bef76502623962c6` | `d8f9994924215770644224b1d89c866ae8fb044be7e94632bef76502623962c6` |
| `render-stage-w2-y-solo-off-restored-02` | `169cbe491b53c9d43f604448cf15b6f9c2ed39993f6614f5d2a725601fa811f4` | `bc28b4aebf64fb8d2b9c4ca9ffaeb3390b441ed492714661a1d2b7dd1035ae2a` | `d8f9994924215770644224b1d89c866ae8fb044be7e94632bef76502623962c6` | `2facdd01fe21bf2fb8db85da062f6db9b7718f7098bdd0ae3bd50b64fcea29e3` |
| `render-poll-w2-y-solo-off-restored-02` | `bc17f68b51961920084601f8f7f484802012c17a8e85d19d1c9d09c03a212a51` | `607367e8622c409ea6ba508198052788b8200dc3c273608382d0d6e0f8bc531b` | `e2b8b00e201fa88884cb7aa5afc2b211490133c80772bd8865e4ae76ac4c9a63` | `e2b8b00e201fa88884cb7aa5afc2b211490133c80772bd8865e4ae76ac4c9a63` |
| `save-checkpoint-w2-restoration-stop-01` | `c0673b83c946fbd200fa5c1bd76c325ac9bdc4f141a48faf08766f1fb7301aeb` | `14615cb48ad95f5bc41ecd4de1b458a37dc5e242d27f0d032d0f48ad987de45e` | `12fa740e15a63da4c54b0d3bedafd9c78b2a0d0415e1c024a29533a96ae2d020` | `12fa740e15a63da4c54b0d3bedafd9c78b2a0d0415e1c024a29533a96ae2d020` |

## Restoration evidence

The producer then attested `BOTH OFF: X A2 mute off then Y A2 solo off; all M/S
off; leave Y current` in `observe-operator-restored-01-20261002-kit-01`.
The native observe result is SHA
`694ffa95cc9e223d4400a2e37e1f9c5347ac1816415de6952902007795b65ca0`; its
pre/post snapshots are byte-equal (SHA
`d8f9994924215770644224b1d89c866ae8fb044be7e94632bef76502623962c6`) and both
show W2-Y-solo current on the Edit page. The neutral Y export
`exports/W2-Y-solo-off-restored-02.otio` has SHA
`0ca7911b5c4b5b8712e212badcdd153a94ac7e8a43510bb73aa65d7570031379` and
machine-readable controls show Audio 1/2/3 enabled with `SoloOn:false` and all
tracks unlocked. Its export evidence journal SHA is
`af3dbeb1b7ffa6905947d9a0d6d5bb9d90cd5884580d8f6b2a25b7b35e38ae6`, with
pre/post snapshots matching the observe snapshot SHA above.

The neutral render was staged as `W2-Y-solo-off-restored-02.mov` under the same
run and its terminal poll is now `Complete` at 100% (job
`3caad583-c2eb-47f2-848c-63758ad8215d`; native poll result SHA
`bc17f68b51961920084601f8f7f484802012c17a8e85d19d1c9d09c03a212a51`). The
output exists (SHA
`3284339a0cd2c675af276d34ff1540c36c784bb34311ed3bd792234c938662b1`, 3,466,328
bytes). The neutral-media analysis is retained in
`out/issue149-workflow-reruns-20261002-kit-01/w2-neutral-y-analysis.json`
(SHA `7999408950a094fc134e89f3df0e218db1acecffcfd00884132461b6e1b491bd`); its focused
`analysis-check.py` invocation passed. It found all 16 fixture words, with
pilots `1000=0.02828`, `1500=0.01986`, and `2000=0.02003`; the render decodes
399 frames from `src_id=1` with zero frame mismatches. Its extracted PCM is
3,064,320 bytes with SHA
`f0e1d5c4dc4c52e2d68d4a7ea92ba683f2c736b5dad059867e86e82dcf203b96`, equal to
the W3 full-program baseline PCM. The full MOV hashes remain different because
container metadata differs, so only PCM equality is asserted. The neutral OTIO
export (SHA
`0ca7911b5c4b5b8712e212badcdd153a94ac7e8a43510bb73aa65d7570031379`) records
Audio 1/2/3 enabled and `SoloOn:false` for all three tracks. Therefore the
neutral-Y media and control gates pass and the required W2 row is complete. A
neutral-X render was not started after the producer’s later read-only guard
found context drift; that extra restoration-assurance case is documented as
unrun below.

## Optional neutral-X extension and retained drift

The resumed continuation first attempted the unique observe config
`observe-final-both-off-03-20261002-kit-01`, which failed inside the injected
harness because the config omitted its required `phase`. Its result SHA is
`c3db0f50a8f95bc225be5801963addaca87278ffdf9d5ca315ffe55e93af44c4`; no
Resolve API call or mutation occurred. A corrected, unique read-only observe
`observe-final-both-off-04-20261002-kit-01` then succeeded; its result SHA is
`83e21501465419330e66e2305b8efb68acb32497ffac341c07f484ee8a00dfb3`, journal
SHA is `ff710bf5ace6f519fad88095735daaa3f899a25d334b6cd8f206f1bf979ca271`,
and its pre/post snapshots are byte-equal with SHA
`59ba860a7403601c22201f4a417b0c67429a5d100dd5db28610a9a4780dfa7ea`.

That fresh read confirmed the named W2-Y current timeline and Edit page, but
found `GetCurrentTimecode() = 00:00:00:00` and audio/video Out marks at frame
399. The prior verified save checkpoint had the same timeline and page at
`00:00:15:24` with empty marks; its SaveProject call returned `True` and its
terminal result SHA is
`c0673b83c946fbd200fa5c1bd76c325ac9bdc4f141a48faf08766f1fb7301aeb`.
Because the required current-context/timecode guard did not match, the actor
did not dispatch neutral-X export/render/poll or another save. The cause of
the later timecode/Out-mark drift is unknown; it is not attributed to any W2
API behavior, and no global pre/post context equality is claimed. The retained
offline comparison is
`evidence/observe-final-both-off-04-20261002-kit-01/drift-comparison.json`,
SHA `08e0830898bd615839c321226c280eb215a476fde8eb560fded52956aa5e5459`.

## Historical producer-requested stopped checkpoint

This section records the earlier pause checkpoint; the resumed continuation and
the optional neutral-X guard are recorded above.

The producer replied **both off**, then requested **stop at checkpoint**. The existing neutral-Y render settled Complete at100%; its output SHA-256 is `3284339a0cd2c675af276d34ff1540c36c784bb34311ed3bd792234c938662b1`. Neutral Y OTIO SHA is `0ca7911b5c4b5b8712e212badcdd153a94ac7e8a43510bb73aa65d7570031379`, with Audio1/2/3 enabled and SoloOn false. X mute-off is producer-attested and its owned context was restored; a neutral X export/render was intentionally not started after the stop request.

The saved checkpoint context was W2-Y-solo UID `bec69cf7-c76e-4820-9e1f-9b425449614f`, Edit page, `00:00:15:24`. `save-checkpoint-w2-restoration-stop-01-20261002-kit-01` called SaveProject once, returned True, and has terminal result SHA `c0673b83c946fbd200fa5c1bd76c325ac9bdc4f141a48faf08766f1fb7301aeb`. The native actor confirms all known render jobs terminal, installed configuration `__disarmed__`, and stopped. Inventory remains13timelines/64items/23media. W4 retime state is intentionally retained. No old #141 project or protected producer clip was modified.

All seven W rows are independently reviewed; W2’s required procedure is
complete and its optional neutral-X extension is explicitly unrun. W3 and W6
remain adverse under their named gates. Neither issue is accepted or closed;
producer acceptance remains separate from this evidence record.
