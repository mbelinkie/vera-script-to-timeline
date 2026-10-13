# Focused candidate checks

Implementation candidate, not final acceptance. Locked CPython3.12.14/uv0.12.5;
synthetic bytes and fake Studio only. No media/native/provider operation.

- Package:15passed3.90s, command `uv run --frozen pytest tests/test_v2_package.py -q --durations=25`.
  Coverage includes immutable build/retry, strict media/path/preparation closure,
  rational rates, multi-track root/child/overlay/return OTIO readback, sample
  mapping/gain policies, metadata tamper, output symlink refusal and retained
  failed staging. Full output in `package-expanded-pass.txt`.
- Combined iteration session63353: `uv run --frozen pytest tests/test_v2_package.py tests/test_workflow_v2.py tests/test_issue177_handoff.py -q --durations=25`.
  Exit1:49passed2failed9.55s. The two failures were fake-adapter interface
  mismatch after a type correction (`add_marker` versus `add_v2_marker`).
  All15package and21parent handoff checks passed, including positive attestation
  and request preparation, changed media, and tampered/rehashed release refusal.
- Corrected Studio rerun:15passed1.33s, exit0. Command
  `uv run --frozen pytest tests/test_workflow_v2.py -q --durations=25`.
  Includes explicit pre-native refusals, Quiet/Full gain readback, reopened
  mismatch, and partial target retention. No guard was weakened to fix the fake.
- Parent final Ruff check and format --check: exit0,9filesformatted.
- Parent final mypy on the8new source/test/helper files: exit0, noissues.

Exact shell prefix for every command above: `rtk proxy ctx-wire run`.
The combined failed run remains failed; these results cover focused iteration
only. Fast gate, required adversarial review and final full qualifying evidence
remain due against the frozen candidate. Current frozen tracked contracts,
fixtures, generated code, accepted tests and v1 helpers have no diff.
