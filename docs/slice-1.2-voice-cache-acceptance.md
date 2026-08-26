# Slice 1.2 Voice Cache — Producer Acceptance

**Producer accepted on 2026-08-25.** The live procedure passed for Matthew
Neural generation, unchanged all-reuse, exactly-one-block invalidation,
normalization and timing provenance, excluded narration, and failed
placeholders. The producer listened to the original and edited assets and
explicitly stated `Accept Slice 1.2`. The independent no-findings review in the
slice plan remains a separate orchestration gate before final closure.

Producer acceptance is authoritative. Agents do not run this live procedure,
choose an AWS data-policy attestation, authorize a billable call, or judge the
voice by listening.

## Prerequisites and bounded inputs

- Use authorized AWS credentials that can call Polly in `us-east-1`.
- The producer selected `provider_terms_accepted` for this acceptance run.
  It remains an explicit per-command attestation and is not a stored default.
- Keep the two canonical Slice 1.1 files read-only. The commands below create
  only `/tmp/vera-slice-1.2-acceptance.script-document.json` and cache entries
  under `/tmp/vera-slice-1.2-acceptance-cache/`.
- Confirm FFmpeg and FFprobe 8.1.2 are the intended producer tools.

The test document combines copies of the two accepted narration blocks so the
same run can prove one-block regeneration while another block remains reused:

```sh
rtk node -e 'const fs=require("node:fs");const torture=JSON.parse(fs.readFileSync(process.argv[1],"utf8"));const minimal=JSON.parse(fs.readFileSync(process.argv[2],"utf8"));const added=structuredClone(minimal.activeDraft.blocks.find((block)=>block.type==="narration"));added.orderKey="a25";torture.activeDraft.blocks.splice(3,0,added);fs.writeFileSync(process.argv[3],JSON.stringify(torture,null,2)+"\n");' \
  tests/data/slice_1_1/torture.script-document.json \
  tests/data/slice_1_1/minimal.script-document.json \
  /tmp/vera-slice-1.2-acceptance.script-document.json
rtk npm run validate:script -- \
  /tmp/vera-slice-1.2-acceptance.script-document.json
```

The validator must pass and list two active narration rows plus the unchanged
excluded narration row.

## 1. Inspect preflight without network or cache writes

Substitute the chosen attestation in every command below:

```sh
rtk uv run --frozen python -m vera_timeline_agent.narration \
  /tmp/vera-slice-1.2-acceptance.script-document.json \
  --cache /tmp/vera-slice-1.2-acceptance-cache \
  --voice-profile aws-polly-matthew-neural-en-us-v1 \
  --aws-data-policy provider_terms_accepted \
  --preflight-only
```

Confirm the preflight identifies two active narration blocks, excludes the
inactive alternative, shows the Matthew Neural profile and voice, dated cost estimate,
`$1.00` ceiling, selected data-policy attestation, and normalization profile.
It must say that no provider call or cache write occurred.

Also prove the named Joanna alternative without synthesis or cache writes:

```sh
rtk uv run --frozen python -m vera_timeline_agent.narration \
  /tmp/vera-slice-1.2-acceptance.script-document.json \
  --cache /tmp/vera-slice-1.2-acceptance-cache \
  --voice-profile aws-polly-joanna-neural-en-us-v1 \
  --aws-data-policy provider_terms_accepted \
  --preflight-only
```

This must show the Joanna profile and `voice: Joanna`, while still saying no
provider call or cache write occurred. Continue the live acceptance with
Matthew.

## 2. Generate and listen

```sh
rtk uv run --frozen python -m vera_timeline_agent.narration \
  /tmp/vera-slice-1.2-acceptance.script-document.json \
  --cache /tmp/vera-slice-1.2-acceptance-cache \
  --voice-profile aws-polly-matthew-neural-en-us-v1 \
  --aws-data-policy provider_terms_accepted \
  --confirm-provider-call
```

The command must report two `status=ready`, `synthesis=generated`, and
`normalization=generated` records. Open and listen to both printed WAV
locators under the cache root. Confirm each is a separate, complete narration
block and neither sounds clipped, silent, distorted, or unexpectedly padded.

Inspect each adjacent `asset.json` and `timing.json`. Confirm the record says
`kind: temp_synthetic`, honestly reports
`voice_version: provider_not_supplied`, records both provider request IDs and
the selected data-policy attestation, and does not claim frame-exact timing.

## 3. Prove unchanged all-reuse

Run the exact generation command from step 2 again. It must report two
`synthesis=reused normalization=reused` records and summary
`generated=0 reused=2`. No Polly request ID or AWS usage should be created by
this run.

## 4. Prove exactly one regeneration

Edit only the copied minimal narration block and its accepted token/anchor
evidence:

```sh
rtk node -e 'const fs=require("node:fs");const path=process.argv[1];const document=JSON.parse(fs.readFileSync(path,"utf8"));const block=document.activeDraft.blocks.find((item)=>item.id==="11000000-0000-4000-8000-000000000004");block.text="Hello worlds.";block.version=2;block.tokens[1].value="worlds";block.tokens[1].endOffset=12;block.hostVisibilitySpans[0].range.quotedText="Hello worlds";block.visualEvents[0].range.quotedText="Hello worlds";fs.writeFileSync(path,JSON.stringify(document,null,2)+"\n");' \
  /tmp/vera-slice-1.2-acceptance.script-document.json
rtk npm run validate:script -- \
  /tmp/vera-slice-1.2-acceptance.script-document.json
```

Run the step 2 generation command again. The edited block must report
`synthesis=generated normalization=generated`; the untouched block must report
`synthesis=reused normalization=reused`. Listen to the edited asset and confirm
the final word changed.

## 5. Confirm exclusion and cache safety

Confirm no asset directory exists for excluded narration block
`12000000-0000-4000-8000-000000000021`, and no request contains `Unused
alternative.` Do not manually modify the cache used for acceptance; automated
tests separately prove that corrupt, linked, partial, or unexpected cache
contents fail closed without deletion or overwrite.

## 6. Producer judgment

Explicitly accept or reject each item:

- voice quality and named Matthew Neural default;
- Joanna Neural availability as a named alternative;
- pronunciation and authored-text fidelity;
- loudness, sample format, and audible completeness;
- timing evidence and its honest precision label;
- unchanged reuse and one-block invalidation behavior; and
- excluded narration and failed-placeholder behavior.

Then explicitly state whether Slice 1.2 is accepted. Until that statement, its
maximum status is **Agent complete** and Slice 1.3 does not begin.
