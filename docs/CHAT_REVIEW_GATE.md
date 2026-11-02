# Producer Chat review verifier (#378)

This branch prepares an independent fail-closed approval gate for `roadmap claim` and agent launches. Approval must be a Producer-authored `VERA_CHAT_REVIEW_V1` record with SHA-256 over `JSON.stringify([title, body])` of the current issue, plus `chat-reviewed`. Unavailable, stale, malformed, or partial comment history is not approval. This document is not itself approval or permission to dispatch.
