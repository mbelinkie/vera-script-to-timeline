# Producer Chat review gate (#378)

This independent implementation verifies **current Chat approval records under the Producer's GitHub identity** before `npm run roadmap -- claim`. It does not claim or launch Codex, approve a PR, or alter status merely from a `chat-reviewed` label.

## Approval contract

The current issue must be open and belong to one of the two configured VERA repositories. It must have `chat-reviewed`, no `chat-review-pending`, and a GitHub comment **actually authored by `mbelinkie`** containing a `VERA_CHAT_REVIEW_V1` JSON record with `producer: "mbelinkie"`, `promptVersion: "1"`, a canonical UTC ISO timestamp (`YYYY-MM-DDTHH:mm:ss.sssZ`) in `reviewedAt`, and `revision` equal to SHA-256 of `JSON.stringify([currentTitle, currentBody])`. The newest attempted Producer HTML approval record supersedes older approvals; if it is malformed or stale, the claim is refused. Ordinary comments discussing the marker name do not revoke an approval.

The gate reads **all** GitHub comment pages using `gh api --paginate --slurp`, validates page sizes and the reported count, re-fetches the issue, then confirms the full comment history again. It refuses changed issue identity, title/body, label set or count, and same-count comment edits/deletions. Roadmap snapshot labels must also match. Missing GitHub data, bad identity, wrong repo, failed API/auth/rate limit, and histories over 2,000 comments fail closed. The gate never stamps `chat-reviewed` on its own. A remaining API-to-mutation race is not transactionally preventable with the current GitHub issue/Project APIs; the re-fetch narrows it, and this should not be claimed as global enforcement against arbitrary direct agent launches.

## How to use

Before any separately configured Codex entrypoint *outside* `roadmap claim`, run:

```sh
node scripts/chat-review-dispatch-gate.mjs https://github.com/mbelinkie/vera-script-to-timeline/issues/378
```

A zero exit means only that the **current** Producer Chat review was verified. It does not set Project status, claim, launch, or approve implementation. Nonzero exits must block the calling launch script. This script is not installed as an OS-wide Codex hook; audit each real launch path and add it to configured paths before asserting broader coverage.

To record an approval, the Producer must complete an interactive Chat review first, finalize the issue's title/body, and post the canonical GitHub approval comment using their authenticated GitHub account, adding `chat-reviewed` only after explicit approval. No agent may approve itself or fabricate the digest. Changing the title/body or adding a DeepSeek handoff **afterward** invalidates the approval and requires renewed review. The approval helper in skipped PR #375 is reference only and is **not installed by this change**.

### Producer handoff without a local approval helper

In the existing interactive Chat review, give Chat the issue URL and ask: "Review and finalize this issue, including its implementation handoff. Show me the final scope and wait for my explicit approval. After I approve that exact revision, record its canonical VERA Chat approval through my authenticated GitHub connection, verify it against a fresh title/body read, and return the approval-comment link. Do not launch work."

The Producer reviews the result and explicitly approves in that Chat. The review assistant then computes the exact JSON/SHA-256 revision mechanically; the Producer does not calculate a digest. Post a **new** comment rather than editing an old approval. If the connection or approval-record capability is unavailable, leave the issue unapproved and stop; the owning Codex task must not substitute its own approval. Current #378 approval comment `6567976817` demonstrates this existing route. This PR does not install #375's helper or require its implementation before review can happen.

### Identity boundary

Approval records must be unedited and have no GitHub App mediation; missing provenance metadata fails closed. These checks detect edited or App-mediated records, but **GitHub account authorship is not proof of which person or agent used a shared credential**. An agent with Matthew's authenticated account could still post a fresh matching record. The mandatory rule against creating one's own approval therefore also relies on agent compliance and the Producer's interactive handoff. Cryptographic human presence, separate GitHub identities and credential isolation are outside this issue's record-verification contract; do not describe this gate as preventing malicious same-account forgery or as a security boundary for paid execution.

## Launcher audit / known limits

Repository entrypoints reviewed: `AGENTS.md` and `CLAUDE.md` instruct agents to claim with `npm run roadmap -- claim`; that path is gated before its Project mutation. The personal `vera-roadmap-dispatch` skill creates visible Codex chats outside this repository; its callers must run the preflight before chat creation. This PR adds that instruction to `AGENTS.md` but does not modify an installed personal skill or desktop runtime. `scripts/ci-queue.mjs` is a CI delivery controller and does not start Codex. `scripts/issue326_workflow_launcher.py` is a separately owned Resolve-native probe, **not** a Codex launcher.

The repo cannot intercept a direct Codex desktop/CLI conversation, another external orchestration service, or a manually started agent which skips `roadmap claim`. A real launcher must invoke the standalone gate itself and refuse a nonzero exit. Until each external caller is verified, this PR enforces **roadmap claim only**, not universal Codex dispatch or claim ownership across all tools. No automatic runner, daemon, or session resume is installed here.

## Verification and integration

Run `npm run test:roadmap`, then `npm run validate:fast` and the normal read-only adversarial Claude review, followed by exact-SHA CI queue validation on a Draft PR. Matthew's current instruction holds required Claude review when capacity is unavailable; it does not waive it or permit merge. Merge only after independent review and readiness through #361. #396's DeepSeek dispatcher must import/reuse this same verifier once merged; its separate actor, issue-level authorization, receipt, budget and Mac gates remain mandatory. This gate performs no paid dispatch and grants no DeepSeek permission. #401 owns dashboard renderer files; none are modified here.
