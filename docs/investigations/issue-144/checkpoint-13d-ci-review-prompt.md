Review one bounded #144 CI plan and ready configuration delta. The user requires Claude reviews and says STOP #144 immediately if your quota runs out. Read-only only; do not execute commands/edit/delegate/use real native/cloud/provider resources. Read/Grep/Glob only.

#144 code/runbook13b and corrective13c reviews passed. The actual full CLI/WI flow and standalone command passed. Local final npm run validate is running on frozen source5b14502, no failure so far,356Python cases. Both GitHub validation jobs were cancelled after15minutes; GitHub's actual annotation is: "The job has exceeded the maximum execution time of 15m0s". Installation/TypeScript/lint/typecheck all passed, Python had reached omission generation at29% with no assertion failure. The existing workflow hard budget is15. Earlier retained local full suite329cases took~46minutes; the current suite has356. This is necessary CI allowance for this slice's actual integration workload, not test skipping/new feature work.

Plan: change ONLY .github/workflows/validate.yml timeout-minutes from15to90. Keep the same pinned runner/actions/runtime, npm/uv locked installation, FFmpeg, all validation commands/tests and lockfile check. Bounded90minutes gives headroom for the measured complete suite; never unbounded, no weakened checks, no extra dependency, sharding or general CI redesign. No harness source/input/contract/golden/provider/native gate changes. The proposed complete file is staged only at /tmp/vera144-proposed-validate.yml; original repo file is untouched pending this review. The eventual one-line implementation will be byte-identical to this reviewed proposal. Final identified-commit CI will run the same npm run validate with the appropriate budget.

Please review BOTH this plan and the exact ready one-line configuration segment, then say if it can be applied as supplied, any blocker, or the smallest required correction. Do not claim you ran tests or that full validation passed. This configuration delta can proceed only if your required review succeeds; no quota bypass/session/account/browser workaround.

Read:
- .github/workflows/validate.yml
- /tmp/vera144-proposed-validate.yml
- /tmp/vera144-ci-cancellation-evidence.json
Consult existing checkpoint13b/13c dispositions only if needed. Keep this bounded; no full source/history reread is needed for the unchanged harness.
