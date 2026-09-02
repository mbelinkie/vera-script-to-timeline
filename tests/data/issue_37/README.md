# Issue 37 fictional prompter fixtures

All content is invented for this slice. No source production script, media,
credentials, or private URL is used.

- `acceptance.script-document.json`: explicit mixed-state OC recording beat,
  a second explicit OC beat, a legacy-derived VO beat, section navigation,
  visible alias/performance annotations, and an opted-out phoneme annotation.
  Export with both inclusion flags enabled.
- `legacy.script-document.json`: the same narration at fictional revision 36
  with both new arrays omitted. Export with both flags disabled.
- Each pair of `.prompter.golden.txt`/`.sidecar.golden.json` files freezes exact
  bytes for that input and settings. Tests never regenerate goldens in place.

State markers preserve editorial coverage; the mixed-state sentence stays one
OC performance beat under the Producer's 2026-09-02 clarification. Full output
and identity rules are in `docs/plans/issue-37-prompter-export.md`.
