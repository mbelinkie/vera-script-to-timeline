# #192 staged dependency identity in the fake synthesis authority

Runtime4 against9c40208a8e054e106e0d899ac0f7038cc82814b8 naturally exited1
with no signal:1 failed in82.19s. Saved log identity matches complete.json:
f1c6d643e28ace6248140ff0d8a0d72c373d2f15b7a14cf2e8c5c91b8148e8f6.
Public A/B inference, both owned C render jobs, and actual independent C
omission verification passed before the synthesis authorization check failed.
Transport and selected #190 regressions were not reached under first-failure
stopping. Full immutable source/input/tool/command/exit evidence remains in
`out/issue192/runtime-4/`.

The new FakeAuthority compared generation binding priorDependenciesHash to
Python compact identity_hash(stage.dependencies). The accepted #191 row
boundary uses compiler sha256CanonicalJson(prior); these formats have distinct
byte identities. Only the new fixture changes: use the existing package's
_compiler_hash for that exact staged-dependency comparison. Request, raw
authorization, service cost and every other authority check remain required.
No production or accepted source/test/fixture/contract changes; no dual-format
acceptance, bypass, rewritten generation input, or fabricated handoff.

Focused Ruff, format and strict mypy pass for the changed fixture, retained
in focused-35-ruff-authority / focused-36-format-authority /
focused-37-mypy-authority. The same bounded serial runtime package must now
rebuild temporary packages/bindings and execute the public test first.
No completed public-path pass, review, fast/full gate, Ready claim or closure
is asserted. Real native/provider/FFmpeg/original-media gates remain excluded.
