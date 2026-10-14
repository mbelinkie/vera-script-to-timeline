# Independent secure-WAV delta review — GO

Actual Claude Opus5.5, high effort, CLI2.1.299 (Claude Code), tools disabled. Source 8d6d478f85739ebe59f11b600fc570e2a5eeb2fc, priorGO53cfffd, accepted202 main deaa75c90b5486e500cb69266faa7bdf09697efc, session cd33f75d-3051-4b86-a627-980edd8495ff. Actual exit0/is_error=false/sourceStillCurrent=true, rawresultSHA256 d35a61cfd935ff263fd93f71aa2755511a885fe4d289f997d3dec685ac08118c. Exact input/source/context/CLI/environment/PID/command provenance remains in out/issue192/claude-3 and review-input-3.json. Both processes naturally drained; all reviewed context pins still match.

## Verbatim reviewer result

# Verdict: **GO** for the secure-WAV fix delta (8d6d478 vs prior GO source 53cfffd)

This approves the narrow fix delta only. It is not acceptance or closure. I read only the supplied source and diff. I executed nothing, and I have not reproduced the reported red, runtime-13 or fast-4 results. The test bodies are consistent with those reported outcomes.

**No blocking findings.**

---

## Prior non-blocking item 1: resolved

`ProofSessionV2._verify_exact_view` (`python/vera_timeline_agent/roundtrip_v2_proof.py:817-833`) no longer calls `wave.open` on a pathname. It now follows the accepted #190 rule (`docs/issue-190-v2-proof-handoff.md:171-174`) and the capture pattern in `_derive_audio` (`roundtrip_v2_native.py:911-928`).

### Link, hardlink and TOCTOU checks
- **Descriptor-safe open.** `_operator_bytes` (`roundtrip_v2_records.py:56-68`) opens the file through `_open_file`. That walk uses an `O_NOFOLLOW` directory descriptor for each ancestor and `O_NOFOLLOW` on the leaf.
- **Independent regular file.** It requires `S_ISREG` and `st_nlink == 1` on the opened descriptor.
- **Unchanged during read.** `_unchanged` checks that dev, inode, size, mtime, ctime and nlink match before the read, after the read, and on a fresh `_regular` path stat. `_regular` also checks every ancestor for symlinks.
- **Post-parse recheck.** `_file_hash(source)` runs again after parsing, through the same descriptor-safe primitive.
- **Parsing uses the hashed bytes.** `wave.open(io.BytesIO(pcm))` parses exactly the bytes that were hashed. The pathname is reopened only for the recheck hash, never for parsing. This matches the stated rule.

### Hash domain
- `digest(pcm)` (`roundtrip_v2_proof.py:51`) computes `"sha256:" + hexdigest` over the whole file. This is the same domain as `_digest` in records and native.
- It is compared with the captured `item["sourceHash"]`, the value that `_derive_audio:913` and `:928` already bind.
- The hash is checked before parsing, so a mismatched file is never parsed.

### Memory bound
- The limit is 64 MiB, the same as capture and the documented bound.
- `st_size <= limit` is checked before reading. The read is at most `limit + 1` bytes, and the length is then checked to equal `st_size`.
- Items are processed sequentially, so only one buffer is live at a time. Unchanged shared limits are not widened.

### Error conversion
- `OSError` (ELOOP, ENOENT or a stat race), `EOFError` and `wave.Error` become `ProofNativeError("reopened audio PCM is unreadable")`, with the cause chained.
- `fact` failures are already `ProofNativeError`, a `RuntimeError` subclass. They are not in the except tuple, so their specific messages survive.
- In CPython 3.12, `wave` converts truncated-header `struct.error` into `EOFError`. Any other exception that escaped would still refuse, so this path fails closed.

### Gain, channel and link semantics
- The link-topology, single-route, `channels in {1, 2}`, gain `== (event["gainDb"] or 0)` and `mono-dual`/`stereo-direct` checks are unchanged (`:810`, `:834-841`).
- Audio items correspond one-to-one to control routes through `_controls(...)` at `native:832`. Capture's `_derive_audio` already parses every route source with the same helper and limit.
- So any observation that legitimately passed capture passes this check. The delta can only add refusals; it cannot add acceptances.

### Callsites and public behaviour
- The function is called only from `evidence()` (`:323`, baseline packet bound to `self.boundary.capture`) and `verify_reopened()` (`:748`, raw read through the receipt-hash pin after `fresh.capture`).
- Both already treat `ProofNativeError` as a refusal.
- The only behavioural change for callers is that malformed or missing WAVs now raise `ProofNativeError` instead of `wave.Error` or `FileNotFoundError`.
- No shared native/records helper, #191/#202 core, contract, fixture, golden or accepted test changed. The imports `_operator_bytes` and `ProofNativeError` follow the existing private-import pattern.

## Regression tests (`tests/test_issue192_proof.py:258-294`)

- **`source-hash`** changes only the observed `sourceHash`; the file is untouched. It must refuse with the exact message "reopened audio source bytes changed" from the pre-parse check. The old code never compared hashes, which is consistent with the retained DID NOT RAISE red result.
- **`invalid-wav`** uses a real independent file `b"not a WAV"` with a matching pin. The hash check passes, then `wave` raises `Error('file does not start with RIFF id')`, which becomes the exact "unreadable" message. That isolates the conversion branch.
- **`gain` and `channels`** are unchanged, as is the positive baseline call at `:272`. The prior 39 cases are preserved and the total is now 41.
- As before, this direct forged raw observation qualifies the comparison guard only. It does not show acceptance of a forged capture.

## Non-blocking notes
1. **Variable rebinding.** At `:817`, `source` is rebound from `event["sourceRange"]` (`:785`) to a `Path`. It is correct, because the range is used only before the rebind and reassigned each iteration, but a distinct name such as `source_path` would read more clearly.
2. **Untested branches at this callsite.** The new tests do not exercise symlink, hardlink, oversize or post-parse-change refusals here. Those branches belong to the unchanged shared primitives already used by capture, so this does not block.
3. **Repeated reads.** A source split into several segments is read and hashed once per audio item. This affects performance only.

## Remaining gates (unchanged by this GO)
- **Final full local gate.** `VITEST_MAX_WORKERS=1 npm run validate` is still required on the exact final reviewed tree.
  - This delta reads WAV/PCM bytes, so it is media-sensitive. Cloud substitution does not apply.
  - Runtime-13 was on 57dd405 and fast-4 on 5490c0a. Reusing either requires the owner's equivalence record showing the later commits are evidence docs only and are not read by any check. The final full run on the final tree settles this.
- **Synthetic delivery only.** Successful fresh delivery and save/reopen is shown only through the explicit integer transport double. The genuine fractional revised native route still truthfully refuses before adapter construction.
- **Fake ports.** All authority, Resolve, provider, cache and probe ports, and the direct audio-view guard evidence, remain unqualified for real native audio save/reopen, acoustic or provider truth, and the #178/#145 Producer gates.
- **D1 for #145.** A real #145 restage must take D1 from actual compiler/finalizer output, not the test-only frame-exact floor division.
- **Workflow gates.** Merge, In-review status and Automated closure still require the retained final full evidence. Exit success alone is not approval.

## Owner disposition

This GO and CLAUDE-DELTA-GO.md together cover the original blocking B1 fixes, N1-N4, actual-D1 gap and secure-WAV follow-up. The reviewed production/test source is frozen. Variable renaming has no behavioral benefit for this acceptance candidate. Link/hardlink/size/postparse race branches remain owned by the unchanged accepted descriptor primitives and are not a new contract. Repeated reads are bounded and sequential; no measured performance failure warrants cache complexity here. No additional code or tests are needed for those nonblocking notes.

The final full local run is required on the final candidate, including newly retained documents; fast/runtime equivalence alone is not acceptance. RealResolve/provider/acoustic/save-reopen and #178/#145 Producer gates remain open.
