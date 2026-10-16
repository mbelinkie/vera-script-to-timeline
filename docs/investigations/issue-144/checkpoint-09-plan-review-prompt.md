Review the checkpoint 9 whole-row narration plan for #144 before implementation.
Read docs/investigations/issue-144/checkpoint-09-narration-plan.md and the relevant
unchanged narration service/cache/projection, script validator/compiler,
roundtrip_build and row-audio policy. The producer has resumed after checkpoint8.

Look for concrete correctness, safety, identity/cache/replay, row-isolation or
scope defects. Is the smallest handoff correctly reusing accepted APIs? Will it
prove complete new row synthesis and fresh timings without contaminating
unchanged rows? Are validation, synthetic labeling and provider authorization
boundaries adequate? Name any blockers before code and the precise minimal fix.
Do not reopen the settled whole-row policy or propose a splice substitute.
Do not claim static review is tests or real-native acceptance. No edits,
commands, native actions, cloud/provider calls or permissions changes.
