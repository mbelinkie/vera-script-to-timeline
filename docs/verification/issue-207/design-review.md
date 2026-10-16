# #207 — static design review and verification

Owner review of the bounded design, not independent code review or actual-app
qualification. No runtime, tests, fast/full, Claude, media or native jobs ran.

## Adversarial review disposition

- **Bootstrap circularity:** accepted #109 result independently rehashed and
  recursively inspected; names exist, UIDs do not. New capture takes separately
  name-bound operator authority; failed downstream observations cannot bootstrap it.
- **Hash self-authentication:** procedure explicitly trusts personal operator
  issuance and separate confirmation. Hashes/issuer fields only bind provenance;
  no claim of cryptographic human authentication.
- **Target ambiguity:** exact name checks precede deeper access; two complete
  independently reacquired reads compare names/UIDs. No global name uniqueness
  claim or unsupported cross-namespace UID uniqueness rule. Transient switch
  away/back and content edits preserving UIDs remain honestly unproven.
- **Replay/concurrency:** exclusive pre-import reservation and exclusive receipt
  consumption make repeats/uncertainty require a new capture. This is a proposed
  local procedure, not a general credential service. Explicit 30-minute choice
  and its retry cost remain Producer judgment.
- **Required restart:** corrected an initial draft contradiction that would
  invalidate every receipt during #109's required request/restart transition.
  A completed receipt can survive that deliberate transition within expiry,
  with renewed operator confirmation and fresh #204 UID checks. Partial attempts
  cannot resume; uncertain history requires fresh capture.
- **Source cycle:** #204 is unmerged and blocked by #208. The design names its
  exact reviewed source prerequisite and accepted-main composition, without
  requiring #204 Closed/Done. Exclusive shared-seam grant, comparison, composed
  commit and delta review precede new runtime work; no edits to its checkout.
  After #192 merged, actual remote main and full/restricted path comparisons
  confirmed its changes do not overlap the six #204 source prerequisite paths.
  The note requires current-main composition preserving accepted #192 changes.
- **Output attacks:** negative cases must use matching authority/request to
  reach genuine overlap checks. Both containment directions, aliases, failed
  retention and safe Console refusal are explicit; untrusted output paths do
  not become authority on failure.
- **Consumer loophole:** receipt-backed authority/request v2 retains all existing
  #204 target/approval guards and binds exact observed receipt, acknowledgement,
  original lineage and expiry. Unchanged v1 cannot claim the new route. No
  automated receipt-to-preflight or preflight-to-effect progression.

No unresolved blocking contradiction found in this static review. The proposed
design has no implementation or Studio evidence. #208's required independent
adversarial review and actual-app acceptance remain separate gates.

## Check scope

These new Markdown files are not executable/check inputs: current package
scripts lint MJS/TS/Python, typecheck source/tests, generate contract schemas,
and run explicit test inventories. Roadmap inspection reads GitHub issue data
and `.github/vera-roadmap.json`; dashboard reads project/config data. Existing
release inventories pin named accepted source/note files, not this new note;
only future #208 will add its pin. No current config/script/input was changed.
VERIFICATION_POLICY's documentation-only rule therefore selects confinement,
whitespace and link/hash checks; no earlier full pass is being reused or claimed.

Final check results and exact note SHA256 are recorded in [README](README.md).
