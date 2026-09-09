# Issue 107 — Resolve Python 3.14 adapter boundary

## Decision under test

Use Resolve's proven injected object through a standard-library-only startup.
Run the native-extension-backed OTIO/package verifier first in VERA's locked
Python 3.12 environment, bind that success to every package file hash and one
fresh project name, then have Resolve recheck the attested bytes before any API
mutation. This preserves the existing external adapter and frozen contracts.

## Automated evidence

The focused boundary suite covers import isolation, external verification
evidence, package-tamper rejection before adapter construction, exact adapter
call order, save/reopen verification, and honest partial-project reporting.
The startup import passes under `python -S`, where third-party site-packages are
unavailable, and asserts that `opentimelineio`, `jsonschema`, and `referencing`
were not imported. The final retained commands and full-suite results appear in
the issue review evidence.

## External evidence

On 2026-09-09, with **External scripting using** retained at **None**, Resolve
launched the staged script through **Workspace > Workflow Integrations**. The
launcher config contained only this checkout's `python/` source path and the
attestation path—no `.venv` or Python 3.12 `site-packages` path.

| Evidence | Observed result |
| --- | --- |
| External verifier | CPython 3.12.14; 5 events, 1 marker, 5 media files; exact hash/size inventory retained in `docs/verification/issue-107/package-attestation.json`. |
| Injected runtime | Issue 6's retained launcher log identified CPython 3.14.7; the same Resolve Workflow Integration runner then loaded this standard-library-only path. `DaVinci Resolve Studio` reported 21.1.0 build 14, and the package inventory was re-hashed before adapter construction. |
| Fresh target | `VERA Issue 107 Acceptance 20260909-163929`; created, configured with an empty manifest-named timeline, saved, closed, reopened, and identity/settings verified. |
| Result | `startup_verified`, `verified: true`, no discrepancies; exact JSON retained in `docs/verification/issue-107/resolve-result.json`. |
| Excluded capability | No media import, event placement, Text+ placement, render, upload, or production-project mutation was performed or claimed. |

An earlier full-build attempt stopped safely before mutation because the
pinned Text+ duration rule was accepted on Resolve 21.0.4 build 5, not 21.1.0
build 14. A second attempt stopped safely because the current disposable
project had no timeline for the inherited full-delivery preflight. Both were
separate from the Python runtime boundary and were not bypassed. The final
startup action removed only those irrelevant full-delivery prerequisites.

The retained successful result contains one stale manual-completion sentence
about the full Text+ build even though `title_placement` is null and the result
message correctly says Text+ was not claimed. That wording was corrected in
code after the run; no additional Resolve project was created solely to refresh
prose evidence.

## Recommendation

**Retain for a future product adapter, with limits.** The result proves a
Python 3.14-compatible, external-bridge-independent injected startup can
consume an externally verified, byte-bound package request and safely create,
save, reopen, and verify a fresh project while external scripting is disabled.
It does not prove the full timeline adapter on Resolve 21.1, because media,
events, Text+, rendering, and product packaging were deliberately excluded.
Those capabilities require their own version-appropriate acceptance evidence;
the 21.0.4 Text+ rule must not be silently generalized to 21.1.
