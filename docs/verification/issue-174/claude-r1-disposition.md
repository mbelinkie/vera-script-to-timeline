# Claude review 1 — FAIL

Reviewed candidate `a640e3f99dd6a68c6565a4404e6abc1b9ccda7d6`, exit 0,
`is_error=false`; exit success did not mean code PASS. Raw result hash
`f3358682fb7f1a1b50c8f836c9cc65831ae7b03959b15b34e2d76189e97e1012`.
Substantive fixes below are implemented but require fresh retained evidence
and exact-revision re-review; no acceptance is claimed yet.

| Finding | Disposition |
| --- | --- |
| F1 tool qualification self-authorized | Public entry point requires an external ledger tying current tool/profile/policy hashes to the exact canonical qualification record hash. Only the explicit private test/qualification trial path can bootstrap measurements; it is not the application entry point. Ledger is written after every qualification case passes. |
| F2 encoder library omitted | Recursively hash the non-system macOS dylib closure; Linux ldd closure is hashed including system-installed codec libraries. Focused fingerprint check confirms actual libx264.165.dylib is present. Adapter source and platform remain pinned. |
| F3 AAC sync reference circular | Retain independent generated-clock residuals for decoded source and output, plus drift. Probe safely interior start/middle/end markers and retain trim-boundary waveform evidence separately. Qualify MP4/MOV/MKV AAC; any measured failure halts qualification. No audio-origin zeroing or tolerance relaxation. |
| F4 torn marker blocks retry | Write/fsync pending marker then atomically rename/fsync directory. Missing/unparseable/incomplete markers are preserved and ignored; valid markers with conflicting verified bytes still refuse. Empty/truncated-marker retry tests added. |
| F5 handle selection unmeasured | Exact decoded ordinal checks for each conversion rate with pre/post handles; qualifier and independently re-decoding verifier share an integer oracle with presentation-interval containment. |
| F6 unqualified colour conversions | Derivation now refuses all classes except qualified yuv420p/limited-range/BT.709. Known SDR same-rate picture reuse retains original bytes. Broader conversion needs separate qualification. |
| F7 same-rate audio | PCM sidecar trims exact requested interval, retaining its position on reused picture's package timeline. Reuse-only refuses new audio bytes; exact published pairs can be reused. New AAC/PCM target-reuse cases verify sample bounds, generated-clock sync and compiler original sample-range handoff. |
| F8 long-source resources | Probe only required frame fields and scale decode/encode timeouts from actual probed/requested duration, preserving cancellation. This reduces full-frame JSON and avoids a fixed ten-minute ceiling; no scheduler/cache/dependency added. |
| F9 picture-only policy | Not adopted silently. Current explicit selected-pair behavior remains; bounded producer-policy proposal #195 is Inbox, not dispatch authorization. |
| F10 coarse exact timebase | Exact integer ticks per source frame use zero tolerance, including 1/Fs. Nonexact coarse timebases still refuse. |
| F11 malformed probes | Inspection converts malformed/missing probe fields into a coded refusal; stub regression test added. |
| F12 evidence independence | Verifier re-decodes hashed retained picture; compiler original sample ranges are compared with receipt source sample endpoints. |

The qualification harness remains synthetic and issue-owned. Frozen contracts,
fixtures/goldens/accepted tests and dependency files are unchanged. Because
production code changed, the prior passing full gate does not cover this new
candidate. Round three runs required final validation with durations retained,
then the exact committed candidate must receive Claude re-review.
