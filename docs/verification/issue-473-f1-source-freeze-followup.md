# #473 F1 source-freeze and read-only SDK handoff — 2026-11-08

**Status:** one real fresh-campaign M4 stage accepted; remaining three
unaccepted. This is *not* #312 acceptance or permission to promote the draft PR.

## Actual native evidence (not a mock)

- Test target: a new sacrificial project created under
  `~/.local/state/vera/issue-473-native-20261108-2319`; different immutable
  project and timeline UIDs from the expired original #473 campaign.
- Real Studio 21.1.1.10 pristine host produced a terminal record and pinned
  receipt. Read-only `resolve_test_bench_m4_runner inspect` returned
  `pristine: verified`, receipt SHA-256
  `c8be94ef54620bb6697e636f537e233657cee8a67bf32542740c55fd1603052f`,
  with operation `62ab5d9f-9834-4092-8e3f-a52574375a49`.
  The next `edited` operation remained `pending`; `revision` and `rebuild`
  were also pending. The report stated `nativeVerified:false` and
  `readyFor312Phase2:false` for the *overall* four-stage campaign.
- Real saved native capture contains 11 unique original item UIDs and six
  tracks. The primary V1 two-clip 327 boundary (0–327 and 327–478)
  is present; the other clips have not been modified.
- The old M4 operation/receipt was **never replayed**. No GUI roll, edited
  host observation, revised inference, rebuilt output or edited MOV/PCM proof
  is being claimed.

## Real preflight failure isolated without bypassing source integrity

- Live official SDK `GetVersion()` returned `[21,1,1,10,""]`. Both the
  read-only edit probe and non-GUI route classifier incorrectly required
  integer values for **all** array entries, rejecting the legitimate fifth
  release-suffix string. Corrected and regression-tested in `4d66cbf0`
  and `1770713b`, still reporting 21.1.1.10 non-GUI roll as unsupported.
- Reauthenticating the pinned pristine session under the updated checkout
  refused `admission seal metadata differs`. Read-only comparison of the
  original immutable HMAC-sealed metadata found exactly the
  `codeSourceGraphSha256` field different:
  - sealed: `5bde3b7746d326f7123a675e8c3734561db2f0254816c75c747e5e155d5568af`
  - now: `bb869275c50e46f530137195cc33fd2e0e7705989c024db221f330ec134427d4`
- `proof_source_hashes_v2()` intentionally hashes **all Python source** as
  well as compiler/contracts/lock inputs. New Python code after admission
  changes the graph. Other seal metadata fields matched. The seal was **not**
  rewritten, forged, disabled or bypassed. The old accepted pristine receipt
  remains preserved, but no future edited proof may be issued from it with
  changed code.

## Code progress delivered and acceptance rule

- `fab9ca4b` adds `prepare_owned_f1_inputs`: a read-only factory under
  the actual shared Resolve owner. It reloads the sealed pristine session,
  verifies signed native capture and the immutable original M4 queue, inspects
  all eleven real SDK item UIDs and six track states, checks the exact
  21.1.1.10 version, and reads the actual playhead. Only non-drop 24-nominal
  timecode at **frame 327** is admitted; a short-lived intent is derived from
  the original four-stage deadline. It never changes a clip, issues an M4
  receipt or triggers AppleScript.
- Tests explicitly reject stale/modified source seals, wrong SDK versions,
  wrong/malformed playhead, completed/replayed later stages and insufficient
  M4 time. Focused Linux suite: **163 passed**. Separate Mac fake-SDK/F1
  safety suite: **111 passed**. Ruff and strict mypy passed. Latest GitHub
  CI at this commit was still in progress at last observation.
- The repository's required one-shot independent review command
  `npm run review -- /tmp/vera473-f1-review-notes.md` was attempted, but
  Claude replied that its weekly limit was reached; **no independent review
  is claimed**.

**Next:** finish actual trusted host OS/TCC/keyboard/window/focus readiness,
one-use F1 dispatch and independent official-SDK save/reopen/edited host capture,
plus revision and rebuild. Only **then** freeze a complete, source-pinned
standalone checkout and create an entirely new unique sacrificial M4 campaign.
Do not hot-update any hashed source file after its new static admission; do not
adopt/reseal the existing pristine state as if it came from that frozen revision.
Do not merge/close #473 or unblock #312/#313 until all genuine M4 acceptance,
real MOV/PCM and independent review are complete.
