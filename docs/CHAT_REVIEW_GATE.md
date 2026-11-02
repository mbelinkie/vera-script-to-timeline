# Producer Chat review gate (#378)

This independent implementation enforces **current, Producer-authored Chat review** before `npm run roadmap -- claim`. It does not claim or launch Codex, approve a PR, or alter status merely from a `chat-reviewed` label.

## Approval contract

The current issue must be open and belong to one of the two configured VERA repositories. It must have `chat-reviewed`, no `chat-review-pending`, and a GitHub comment **actually authored by `mbelinkie`** containing a `VERA_CHAT_REVIEW_V1` JSON record with `producer: "mbelinkie"`, `promptVersion: "1"`, an ISO-ish parseable `reviewedAt`, and `revision` equal to SHA-256 of `JSON.stringify([currentTitle, currentBody])`. The newest Producer marker supersedes older approvals; if the newer one is malformed or stale, the claim is refused. A subsequent ordinary comment does not invalidate an approval.

The gate reads **all** GitHub comment pages using `gh api --paginate --slurp`, requires the retrieved count to equal the issue's reported count, re-fetches the issue, and refuses if title/body, label set, or count changed during the verification. Missing GitHub data, bad identity, wrong repo, failed API/auth/rate limit, and histories over 2,000 comments fail closed. The gate never stamps `chat-reviewed` on its own. A remaining API-to-mutation race is not transactionally preventable with the current GitHub issue/Project APIs; the re-fetch narrows it, and this should not be claimed as global enforcement against arbitrary direct agent launches.

## How to use

Before any separately configured Codex entrypoint *outside* `roadmap claim`, run:

```sh
node scripts/chat-review-dispatch-gate.mjs https://github.com/mbelinkie/vera-script-to-timeline/issues/378
```

A zero exit means only that the **current** Producer Chat review was verified. It does not set Project status, claim, launch, or approve implementation. Nonzero exits must block the calling launch script. This script is not installed as an OS-wide Codex hook; audit each real launch path and add it to configured paths before asserting broader coverage.

To record an approval, the Producer must complete an interactive Chat review first, finalize the issue's title/body, and post the canonical GitHub approval comment using their authenticated GitHub account, adding `chat-reviewed` only after explicit approval. No agent may approve itself or fabricate the digest. Changing the title/body or adding a DeepSeek handoff **afterward** invalidates the approval and requires renewed review. The approval helper in skipped PR #375 is reference only and is **not installed by this change**.

## Verification and integration

Run `node --test scripts/chat-review-current.test.mjs`, `npm run test:roadmap`, then `npm run validate:fast` and the normal read-only adversarial Claude review (or document unavailability), followed by exact-SHA CI queue validation on a Draft PR. Merge only after independent review and Producer/integrator readiness through #361. #396's DeepSeek dispatcher must import/reuse this same verifier once merged; its separate actor, labels, receipt, budget and Mac gates remain mandatory. #401 owns dashboard renderer files; none are modified here.
