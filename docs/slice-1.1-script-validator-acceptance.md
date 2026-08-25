# Slice 1.1 Script Validator — Producer Acceptance

Producer acceptance is authoritative. Run this procedure only after the agent
reports focused and full repository checks green.

## 1. Validate both canonical inputs

From the repository root:

```sh
rtk npm run validate:script -- \
  tests/data/slice_1_1/minimal.script-document.json
rtk npm run validate:script -- \
  tests/data/slice_1_1/torture.script-document.json
```

Each command must exit zero, print `PASS ScriptDocument valid`, and list every
active-draft block with a one-based row number, block type, order key, and ID.

## 2. Create a deliberately broken temporary copy

This procedure writes only `/tmp/vera-slice-1.1-broken.json`; it does not modify
the canonical input.

```sh
rtk cp tests/data/slice_1_1/minimal.script-document.json \
  /tmp/vera-slice-1.1-broken.json
rtk node -e 'const fs=require("node:fs");const p=process.argv[1];const d=JSON.parse(fs.readFileSync(p,"utf8"));const n=d.activeDraft.blocks.find((b)=>b.type==="narration");n.visualEvents=[];fs.writeFileSync(p,JSON.stringify(d,null,2)+"\n");' \
  /tmp/vera-slice-1.1-broken.json
```

## 3. Confirm the exact failure

```sh
rtk npm run validate:script -- \
  /tmp/vera-slice-1.1-broken.json
```

The command must exit nonzero and report:

- `FAIL ScriptDocument invalid`;
- diagnostic code `VOICEOVER_VISUAL_GAP`;
- `Row 2`, order key `a1`, and the narration block ID; and
- the affected token range
  `11000000-0000-4000-8000-000000000005..11000000-0000-4000-8000-000000000006`.

## 4. Producer judgment

Confirm that the pass output is readable, the broken-copy complaint identifies
the correct narration row and token range, and no default or automatic repair
was applied. Then explicitly accept or reject Slice 1.1. Acceptance freezes the
two canonical Slice 1.1 inputs for reuse by Slice 1.3 compiler goldens.
