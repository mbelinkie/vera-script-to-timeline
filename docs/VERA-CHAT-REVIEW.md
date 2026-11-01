# VERA: Producer-controlled Chat review before Codex

## Contract

No Codex task may be **claimed** through `scripts/roadmap.mjs` until the current issue version has a verified Chat review approved by the Producer (`mbelinkie`). Starting a ChatGPT conversation is **never an approval**. Producer feedback and revisions remain part of the interactive conversation; do not autonomously close review, apply a label, move Ready, claim, implement, or approve a release.

This gate is distinct from release milestone sign-off: **every working release still requires explicit Producer review and approval** before the release milestone can complete. Implementers may continue within separately agreed issue scope after the issue's Chat review and normal roadmap dispatch authorization.

## Dashboard behavior

- **Not reviewed** — no review label; link to a new ChatGPT conversation with standardized prompt.
- **Pending Producer** — optional `chat-review-pending` GitHub label (not applied merely by opening the link).
- **Approved** — `chat-reviewed` label **and** a Producer-authored GitHub comment containing `VERA_CHAT_REVIEW_V1` and the SHA-256 digest of the current exact GitHub issue *title and body*.
- **Outdated** — approval record exists but title or body changed since approval.
- **Unverified** — a `chat-reviewed` label exists but no matching Producer-authored versioned approval record can be verified (or GitHub could not be reached). The system must fail closed.

Review state is displayed on queue rows and per-board cards; queue filter offers every state. Dashboard reads are read-only and refresh normally. Stale status is based on issue *title/body*, not `updatedAt`; additional issue comments, GitHub label changes, and project changes alone do not stale approval.

The dashboard's **Review in ChatGPT** link opens `https://chatgpt.com/?prompt=...` in a new browser tab, with a versioned review prompt and issue URL. This prefilling mechanism is not a guaranteed native ChatGPT app contract, may change, and may require an extra Send click. **Copy prompt** provides a fallback for ChatGPT desktop app or URL failures. The local dashboard never submits Chat reviews or approvals to ChatGPT automatically.

## Review conversation

1. Click **Review in ChatGPT**, review the issue, discuss scope, dependencies, acceptance and appropriate milestone.
2. ChatGPT proposes changes and asks questions. Producer may keep revising for as long as necessary. This stage does not label anything approved.
3. Producer explicitly says: `I approve this Chat review for vera-script-to-timeline#125.` (or the actual repository and number). ChatGPT should only then attempt to record approval, **if GitHub write permissions exist**. No implementation/PR merge is implicitly authorized.
4. If the ChatGPT GitHub connector cannot write, use the interactive fallback below after approval.

## Setting up labels

Create these two GitHub issue labels in **both** VERA repositories (not GitHub Projects fields):

```sh
gh label create chat-reviewed -R mbelinkie/vera-script-to-timeline --color 2da44e --description 'Producer-approved current Chat review'
gh label create chat-review-pending -R mbelinkie/vera-script-to-timeline --color d4a72c --description 'Chat review in progress; awaiting Producer'
gh label create chat-reviewed -R mbelinkie/vera-research-video-clips --color 2da44e --description 'Producer-approved current Chat review'
gh label create chat-review-pending -R mbelinkie/vera-research-video-clips --color d4a72c --description 'Chat review in progress; awaiting Producer'
```

If a label already exists, do not overwrite it; check it first.

## Local approval fallback (when GitHub plugin writes are forbidden)

In the **actual VERA repository checkout** after the Producer has explicitly approved in conversation:

```sh
node scripts/chat-review-approval.mjs approve \
  --issue https://github.com/mbelinkie/vera-script-to-timeline/issues/125 \
  --summary 'Producer approved scope, dependencies, failure cases and acceptance criteria after interactive Chat review.'
```

This requires `gh auth login` as `mbelinkie` and an **interactive terminal**. The Producer must personally type the full confirmation shown by the command. It then fetches the current issue version, posts a public summary with its fingerprint, adds `chat-reviewed`, and reads back the result. It does **not** copy private Chat transcripts into the public issue. An agent/noninteractive process cannot invoke this approval mode.

Check before Codex work in another execution environment:

```sh
node scripts/chat-review-dispatch-gate.mjs --issue https://github.com/mbelinkie/vera-script-to-timeline/issues/125
```

The existing `npm run roadmap -- claim <issue> ...` path is patched to enforce this verification from the GitHub issue snapshot. The label alone is insufficient. A directly launched Codex session that **bypasses the VERA claim command** cannot be prevented by a local dashboard; configure all dispatch/orchestration entrypoints to call the standalone gate. A GitHub branch rule or Actions job can optionally enforce the same gate on PRs. Do not claim this protects unrelated manual workflows until those entrypoints are wired.

## Integrity, availability and limitations

- Approval is public GitHub issue-comment evidence. `author.login` must be the configured Producer; arbitrary `chat-reviewed` labels or non-Producer comments never validate.
- Edits to title/body after approval require a new interactive review. Comment additions do not.
- The dashboard currently audits the latest 100 comments for each labeled issue; if a historical approval is pushed farther back, it fails closed as **Unverified** until reapproved or a dedicated pagination extension is made.
- GitHub errors display **Unverified** and never create a false green review. The dashboard refresh does not change GitHub.
- This is a **human-specified process control**, not cryptographic proof that a private ChatGPT conversation took place. The GitHub account owner can still manually edit labels/comments; signed review verification protects normal operations from accidental approvals, not malicious privileged GitHub administrators.
- Neither the review nor the `chat-reviewed` label implies authorization to spend money, run Resolve, mutate media, modify project order, merge code, or mark a release complete.

## Test

```sh
node --test scripts/chat-review.test.mjs scripts/project-progress.test.mjs
npm run test:roadmap
```
