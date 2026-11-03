# Producer Chat approval handoff

Use this procedure when preparing, reviewing or recording approval of a VERA
issue. The human confirmation can be conversational; the saved approval must
still be verifiable against the exact current issue revision.

## Finalize before asking

1. Read the current issue, existing implementation/claims and relevant rules.
   Finish the Chat review and surface unresolved product, taste, money or
   private-data decisions.
2. Finalize the title/body, implementation handoff, `Acceptance criteria` and
   canonical `Dependencies` section. Use `None` only when there are no actual
   blocking dependencies. Check the roadmap tool accepts the format **before**
   requesting approval. Do not create repeated approval work through avoidable
   formatting edits afterward.
3. Show the final scope and material limits in the conversation. If a new edit
   changes that scope, show the change before treating a go-ahead as approval.

For new coding tickets, use Chat to prepare the DeepSeek route. Confirm the
coding classification and turn the first suitable change into a bounded task
with frozen checks and a named integration owner. Apply the existing
[DeepSeek dispatch requirements](DEEPSEEK_CHAT_DISPATCH.md) to that task,
including separate approval of the exact live task and its spending limit.
Continue already-owned work with its original owner. If the worker's current
scope or a documented route override blocks the task, explain that constraint
in Chat and settle the handoff there.

## Accept an ordinary go-ahead

A direct Producer instruction such as "launch #396", "go ahead", or "these
two are ready for Codex" is sufficient confirmation when it unambiguously
refers to the final, Chat-reviewed scope already presented. Multiple named
issues can be approved together. Require no exact sentence, typed passphrase
or second confirmation merely to record the approval.

Preparation requests, quoted third-party text, eligibility labels and automated
events are not Producer approval. If scope was not reviewed, the reference is
ambiguous or an unresolved consequential decision remains, ask only about that
specific missing point. An implementation go-ahead is not paid-job permission.

## Record and verify

The interactive Chat review assistant records the approval as the mechanical
completion of the Producer's instruction. Cite that instruction's provenance,
re-read the final title/body, compute the canonical V1 revision, post a new
approval comment through the authenticated approved path, update review labels,
and verify the stored record against a fresh read. Return the approval link.
Use the canonical review verifier; this procedure does not replace it.

The implementing Codex agent verifies that record before launch/claim; it does
not manufacture its own approval. If the recording capability is unavailable,
report that precise handoff failure. A body/title change still requires a new
matching record; no stale-hash exception or silent approval migration is added.
When scope changes materially, obtain a new Producer go-ahead on the change.

Approval permits normal readiness/claim consideration. Existing ownership,
dependencies, separate paid-job authorization, tests, independent review, CI,
merge and acceptance gates continue to apply. Shared GitHub-account authorship
does not cryptographically distinguish a human from an agent using that account.
