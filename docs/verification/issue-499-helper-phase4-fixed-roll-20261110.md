# #499 phase 23/31 - fixed Swift Roll actuator

Plan SHA-256: 816b5dd17611d5b8198a453ce6fe687d12c201f2438a2d6d88ed6a8e5617be18.
Adopted PR #474; branch zodex/499-adopt-pr474; starting head ebc46f8d.
Scope: code and simulated Accessibility only. No live Resolve edit, case or M4 receipt.

Closed canonical RollRequest binds operation, case, PID/window, deadline, source and actor pins.
Native gate checks running helper SHA-256, code-directory hash, team and signing requirement.
Frozen LaunchAgent actor/source pins are not yet configured; absent pins refuse live dispatch.
Literal menus: Edit Deselect All (if enabled), absolute Auto Deselect All Tracks, V1 toggle,
Trim Normal Edit Mode, then Trim Roll Start to Playhead. Slash in V1 title remains literal.
Fresh PID/generation/window/focus/modal/menu validation precedes every attempt.
Durable one-use intent marker: private owner-only O_EXCL, file and directory fsync.
Attempted steps and individual AX results are journaled durably; never retry uncertain AXPress.
Reply is dispatched-unknown, not independent native edit proof.

Native Swift check-compile.sh PASS; check-contracts.sh: 16 focus + 76 fake-AX Roll PASS.
Mutation disabling consumed-intent claim killed by spent-intent replay test; guard restored.
Earlier focused Linux helper/GUI regression: 109 passed. Full fast gate deferred to Phase 8.
Candidate helper source manifest: 4bd5ccbe3ffdaaba927818d143e5ceddb8240d7de05831d18783d813fe36207c (17 files).
RollActuator.swift SHA-256: 0dc29e006516102527c75b387366897a09cdfc624a216ef320b6f042ef95cd44.
Prior Phase-22 signed binary does NOT match this Phase-23 source; no native dispatch.
Next: Phase 24 production-seam migration, code and simulated tests only.
Conductor LaunchAgent is stopped and disabled until explicit Producer resume.
