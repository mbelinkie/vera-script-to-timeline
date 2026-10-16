# Future test coverage audit — 2026-10-04

Read-only intake requested by the producer during #144. Queried all148 open and
closed repository issues and all145 items on configured GitHub Project2. No
issue creation, edit, reprioritization or dispatch. All5 areas have live owners.

| Discussed outcome | Coverage | Owner / current status | Exact remaining test definition |
| --- | --- | --- | --- |
| Spanning music | Partially covered | #100 Inbox | Generic primary/safety tests are required; spell out cross-row duration/order changes and complete mix/placement acceptance in its later plan. #153 already requires explicit spanning-music treatment in row-edit design. |
| Curated graphics | Covered | #8 Blocked | Explicit typed-value/asset/placement/duration/save-reopen and external visual checks; #7 accepted compiler, #9 authoring, #10 Free fallback have separate ownership. No blanket arbitrary-graphics support. |
| Transitions | Partially covered | #88 Inbox | Declared policy/overrides/handle/anchor/atomic consequences and unknown-native refusal are tracked; exact real expanded-round-trip tests must be refined with #125/#137/#128/#138/#139 accepted authorities. |
| Post-prompter edits/reshoots | Covered | #153 Inbox | Explicit producer walkthrough covers export lock, override, whole-row replacement, failures, reshoot indication, unchanged beats and changed-row export. Implementation ownership is to be settled through its accepted design. |
| Untouched-work preservation | Partially covered | #104 Inbox | Selective regeneration and focused safety tests are named; define actual retained human-finishing/untouched-row/source/local-cut invariants and real verification before Ready. Current #144 fresh-target content equality is not that full claim. |

The3 partial areas are refinements of existing owners, not missing ownerless
features or new dispatch authorization. #144's sample remains the bounded
three-edit proof. Do not pack every later functionality into the real sample or
claim those future test scenarios are already written/passing.
