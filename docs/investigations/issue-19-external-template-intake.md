# Issue 19 — external template intake and project-scoped reuse design

Status: proposed design for Producer acceptance; no production contract or
implementation is authorized by this document.

## Decision in one sentence

VERA should admit an externally authored template only as a validated,
content-addressed immutable package revision, then copy an authorized exact
revision into each destination as a project-owned immutable snapshot whose
bytes may be physically deduplicated but whose availability, name, lifecycle,
and permissions are independent of the source project.

This chooses the issue's **project-local immutable snapshot** option. A
governed live reference is rejected for project creation because later source
withdrawal, rename, permission loss, or current-revision movement could change
whether an existing destination project can reproduce its uses. The Producer
must explicitly accept this decision before any intake, project-library, or
cross-project copy implementation begins.

## 1. Authority, terms, and non-goals

### 1.1 Binding inputs

- GitHub issue #19 defines the outcome, required scenarios, exclusions, and
  unresolved copy decision.
- The product specification defines immutable dependency revisions, paths as
  locators rather than identity, project-scoped template items, exact revision
  pins, resolved snapshot hashes, and the rule that newer revisions never
  rewrite existing uses, checkpoints, or builds.
- Accepted issue #13 defines independent project authorization, safe discovery,
  authorization-valid DOM presence, hosted Web/local-agent capability language,
  and the rule that renderer visibility is not authorization.
- The curated Fusion plan demonstrates the later separation among registry,
  package validation, compiler contracts, placement, and authoring UI. Its
  Fusion-specific controls are not generalized or implemented here.

### 1.2 Terms

| Term | Meaning in this design |
| --- | --- |
| External package | Bytes assembled outside VERA and presented through the intake boundary. VERA never designs, animates, converts, or repairs them. |
| Package revision | One immutable manifest plus its exact declared file set, identified by a canonical package digest. |
| Registered revision | A package revision that passed the validator profile named in its validation receipt and is eligible for explicitly authorized project attachment. |
| Project template | A project-owned library identity with a project-local name and lifecycle. |
| Project template revision | An immutable project-owned snapshot of one registered package revision. It pins the package digest and validation receipt. |
| Current revision | A convenience pointer for new selections only. It never changes an existing use or copied selection. |
| Template use | An authoring occurrence that pins one project template revision plus the resolved semantic snapshot required by the product specification. |
| Copy | Creation of a destination-owned project template/revision from an exact authorized source revision. Copy does not mean live inheritance. |
| Physical deduplication | Reusing content-addressed object bytes behind independent logical snapshots. It never shares authorization or lifecycle. |

### 1.3 Non-goals

This design does not choose a native authoring format, define semantic controls,
validate an actual Fusion/After Effects/OGraf graph, render a reference image,
create a role system, mutate a project, implement storage, define browser
screens, compile a graphic, or place anything in Resolve. It does not introduce
the deferred workspace standards/override system. It defines only the boundary
later slices must preserve.

## 2. Intake package boundary

### 2.1 Accepted package forms

The first registration contract should accept exactly two transport forms with
the same logical contents:

1. an intake directory used by an authorized operator or trusted local intake
   tool; or
2. one non-self-extracting ZIP archive with a single package root.

The canonical registered form is the verified file set, not the directory path,
archive filename, ZIP metadata, or upload event. A loose native template file,
installer, executable archive, remote URL, mutable cloud document, or source-
application project is not a package. It must first be assembled externally
into the declared envelope. Intake never runs an installer, macro, script,
expression, plugin, or native authoring application.

The envelope is format-neutral. A payload may declare a native format only if
a separately approved validator profile supports that exact format and version.
Unknown formats or validator profiles remain quarantined; VERA does not convert
them to a supported format.

### 2.2 Required root manifest

The root manifest is a proposed later contract and must contain at least:

| Field family | Required evidence |
| --- | --- |
| Envelope identity | Manifest schema/version, package kind, stable external lineage key, human display name, and external revision label. Human labels are never revision identity. |
| Exact bytes | Relative POSIX path, byte length, media type, and SHA-256 digest for every file; one declared payload entry point; no undeclared file. |
| Authorship/provenance | Declared author/publisher, producing organization, source tool and version, external source revision or release reference when one exists, package creation time as audit metadata, and the intake actor's attestation. |
| Validator/compatibility | Required validator profile/version, native format/version, supported application/edition/version range, platform constraints, template kind, semantic-schema locator, timing/layout capabilities, and declared fallback class when applicable. |
| Dependencies | Every bundled or external asset, font, plugin, script/runtime requirement, and other package dependency with exact identity, version/range, required/optional status, and resolution policy. |
| Rights | Rights holder or supplier, rights basis, allowed VERA projects or organization scope, modification/redistribution/embedding permissions, attribution, territory/time restriction when applicable, and a declaration for every asset and font. |
| Evidence | Reference-render locators and digests when required by the validator profile, plus any publisher signature and verification chain. A signature is evidence only when verified; its mere presence grants no trust. |

Timestamps, filenames, display names, publisher claims, and external revision
labels are audit/search data, not package identity. Secret values, credentials,
local absolute paths, signed download URLs, and source-project permission claims
must not enter the manifest.

### 2.3 Revision identity

The canonical package digest is computed from:

1. the manifest normalized by the later contract's canonicalization rule, with
   the package-digest field omitted; and
2. an ordered list of every declared relative path, byte length, and content
   digest.

The later contract must pin the hash algorithm and canonicalization version.
Any byte, declared dependency, rights statement, semantic schema, compatibility
claim, or manifest field covered by canonicalization produces a different
package digest. Repacking identical logical contents may deduplicate to the same
digest; changing only a filename still changes the identity because paths are
part of the declared package surface.

VERA mints an internal registered-revision ID after successful validation, but
the package digest remains the cross-system evidence. A human revision number
may be duplicated or incorrect and never selects bytes.

### 2.4 Licensing declarations and gates

- Every payload, asset, and font must be covered by a declaration. “Unknown” is
  a visible quarantine reason, not an implicit approval.
- Bundled font bytes require declared embedding and redistribution authority.
  A system-font dependency requires an exact family/style identity, compatible
  substitute policy of `none` by default, and later environment validation.
- A license allowing one source project does not authorize cross-project copy.
  Copy eligibility is the intersection of current actor authority, destination
  policy, and the recorded rights scope.
- Attribution and expiry/territory restrictions remain attached to every
  project snapshot and build snapshot that uses the revision.
- Administrative withdrawal never falsifies past evidence. A legal or rights
  hold may block new copies, new placements, or new builds while retaining the
  immutable revision and references needed to explain prior builds.

This is a declaration-and-gate design, not legal advice or a full digital-rights
management system. A later rights workflow may add review evidence without
changing revision identity retroactively; a changed rights declaration creates
a new package revision.

## 3. Validation, quarantine, and failure reporting

### 3.1 Intake lifecycle

```text
received bytes
    |
    v
staged (not discoverable by projects)
    |
    v
structural and safety validation
    |
    +---- failure ----> quarantined
    |
    v
format/profile validation
    |
    +---- failure ----> quarantined
    |
    v
rights and compatibility review
    |
    +---- incomplete -> quarantined
    |
    v
validated -> registered -> explicitly attached/copied to selected projects
                 |
                 +---- later hold/withdrawal -> unavailable for new attachment
```

Quarantine is an intake state, not a partially usable library. Quarantined
bytes are access-controlled, absent from project selectors, unavailable to the
compiler/local agent, and retained only under a bounded evidence/retention
policy. Corrected contents are a new intake candidate with a new digest; VERA
never edits a quarantined package in place.

### 3.2 Fail-closed validation stages

| Stage | Required checks | Failure behavior |
| --- | --- | --- |
| Transport safety | Bounded archive/file count/expanded bytes/path depth; one root; no absolute/traversal/case-colliding paths; no symlinks, hard links, devices, sockets, nested executable archive, or undeclared file. | Quarantine before extraction or promotion. |
| Manifest integrity | Supported manifest schema; unique normalized paths; exact size/hash for every file; required entry points; no secrets or absolute locators. | Quarantine with manifest and path diagnostics. |
| Payload safety | Allowed media/native file types for the validator profile; no executable/plugin/script content unless a later profile explicitly permits and sandboxes it. | Quarantine; never execute to determine validity. |
| Dependency resolution | Exact bundled dependency hashes; allowed external dependency kinds; fonts/plugins/assets declared; no missing required dependency. | Quarantine or `incompatible`, never substitute. |
| Format/profile validation | The separately approved adapter confirms declared format/version, semantic schema bindings, reference evidence, graph/control identity, and format-specific invariants. | Quarantine with stable profile-specific codes. |
| Compatibility | Declared target application, edition, version, platform, capabilities, timing/layout, and fallback intersect the destination policy. | Registered revision may exist but is ineligible for an incompatible project; the reason remains visible. |
| Rights review | Complete declarations and an allowed intake/copy scope. | Quarantine or rights hold; no project attachment. |

Validation proves conformance to the named validator profile, not artistic
quality, universal safety, or compatibility with untested versions. The receipt
therefore pins the package digest, validator profile and version, ruleset
digest, execution environment/capability evidence, result, findings, actor/job,
and completion time.

### 3.3 Failure report contract

Every failure report should include a stable code, stage, severity, safe
relative path or manifest pointer, expected condition, observed condition with
secrets removed, validator/ruleset version, package digest when computable, and
one bounded remediation. Reports must distinguish:

- invalid package;
- missing required bytes/dependency;
- unsupported format or validator profile;
- target incompatibility;
- incomplete/denied rights;
- malicious or unsafe envelope;
- transient validator infrastructure failure; and
- authorization denial.

Infrastructure failure is retryable against the same staged digest; content or
manifest failure requires a new candidate. No failure path chooses another
revision, repairs a package, or publishes a partial template.

## 4. Project-template data model and lifecycle

### 4.1 Conceptual entities

These are design entities, not approved production schemas:

| Entity | Identity and purpose | Mutable state allowed |
| --- | --- | --- |
| `ExternalTemplateLineage` | Groups publisher-declared revisions for discovery. It cannot select bytes. | Display metadata and governance state may advance through audited events. |
| `RegisteredPackageRevision` | Immutable package digest, manifest, validation receipt, provenance, rights, compatibility, and content-addressed bytes. | No field mutates; a hold/withdrawal is a separate lifecycle event. |
| `ProjectTemplateItem` | Project-owned library identity and display name, with lineage metadata and optional current-revision pointer for new placements. | Name, description, current pointer, and active/retired state change through authorized audited commands. |
| `ProjectTemplateRevision` | Immutable destination snapshot of one registered package revision, including project ID, package digest, source receipt, copy actor/time, source-project evidence when copied, and destination rights decision. | Nothing; corrections create a new revision. |
| `ProjectTemplateUse` | Exact project-template-revision pin plus semantic inputs/occurrence settings and resolved snapshot hash. | Authoring changes create a new document revision; existing checkpoints/builds remain unchanged. |
| `TemplateLifecycleEvent` | Append-only registration, attachment, copy, supersession, retirement, hold, withdrawal, or restoration evidence. | Nothing. |

The future Phase 9 contract should reconcile these concepts with the
specification's `TemplateItem`, `TemplateRevision`, `GraphicTemplatePackage`,
and `GraphicUse`, rather than adding a parallel production model incidentally.

### 4.2 Ownership and availability

- A `ProjectTemplateItem` and every project-template revision belong to exactly
  one authoring project. Project membership and template-management capability
  are evaluated by that project's API on every request.
- A registered revision is not workspace-global library access. It becomes
  usable only after an authorized explicit attachment/copy creates the
  project-owned snapshot.
- A project may physically reuse content-addressed bytes, but authorization is
  checked against the project snapshot before locators or bytes are issued.
- A library list may expose only fields the current actor may discover. A name,
  thumbnail, lineage key, source-project ID, or stale selection token is never
  permission to read, copy, render, or build the revision.
- The destination project gains only its copied immutable revision. It gains no
  membership, browsing access, history, future updates, or current pointer from
  the source project.

### 4.3 Supersession, retirement, withdrawal, and reproducibility

| Event | New placements/copies | Existing uses/checkpoints/builds |
| --- | --- | --- |
| New revision published | May select the new exact revision after validation and authorization. | Stay pinned to the old revision until an explicit per-use migration creates a new document revision. |
| Current pointer advanced | New picker default may change with a visible `Update available` state. | No change. |
| Project item retired | Hidden from ordinary new placement and new-project copy. | Immutable revisions and pinned uses remain resolvable. Restore is an audited event. |
| Registered revision withdrawn | Block new project attachments/copies. | Existing project snapshots remain retained; ordinary withdrawal does not revoke them. |
| Rights/security hold | Block the actions named by the hold, potentially including new builds, while showing a precise reason. | References and prior build evidence remain retained. No silent substitution or deletion. |
| Project deleted under a future retention policy | Outside this issue. | A later destructive-retention design must protect retained checkpoints/builds and audit requirements. |

Existing reproducibility means VERA can identify and retrieve the exact retained
bytes and dependency evidence used by an authorized existing project. It does
not mean VERA may ignore a current legal/security hold or promise that an
external application version can execute forever.

## 5. Copy-model decision

### 5.1 Options

| Option | Reproducibility | Permission behavior | Operations | Decision |
| --- | --- | --- | --- | --- |
| Governed reference to organization/source revision | Destination can break when source access, policy, or lifecycle changes unless governance becomes workspace-global. | Easy to accidentally turn current source visibility into continuing destination access. | Central updates are simpler, but rollback and source/destination outages are coupled. | Reject for project creation. |
| Project-local immutable snapshot | Destination pins exact bytes and evidence; source changes cannot rewrite it. | Copy is one explicit authorization decision; later reads use destination authority only. | More lifecycle records, while physical bytes can still deduplicate. | **Adopt.** |

### 5.2 Snapshot invariants

1. Selection identifies an exact source project-template revision and package
   digest, never `current` by itself.
2. Copy reauthorizes the actor, source revision, rights scope, compatibility,
   and destination immediately before commit.
3. Commit creates a destination item/revision and append-only copy evidence in
   one idempotent transaction. Object bytes may deduplicate by digest.
4. The destination revision remains valid independently of later source rename,
   retirement, membership removal, or current-pointer movement.
5. No source history, future revision, membership, or permission is inherited.
6. A later update is another explicit exact-revision copy followed by explicit
   per-use migration; it is never background synchronization.

## 6. Authorization boundaries

Role names remain a later authorization decision. The implementation contract
should enforce capabilities so it can map the specification's Producer and any
later suite/project administrator roles without broadening either.

| Action | Required capabilities and rechecks | Explicit denial |
| --- | --- | --- |
| Stage/intake package | `template:intake` in the governing registry scope plus authority to attest provenance/rights. | Project Producer authority alone does not grant global intake. |
| Approve registration/hold/withdrawal | Separate `template:register` governance capability; two-person policy may be added later. | Intake actor is not implicitly an approver. |
| List project templates | Current membership plus `template:discover` for that project. | Discovery returns no private source details beyond authorized fields. |
| Manage project library | Current destination membership plus `template:manage`. | Source membership does not grant destination mutation. |
| Create project | `project:create` in the intended parent/suite scope. | Knowing a project/template name grants nothing. |
| List copy candidates | `template:discover` in each source and rights-compatible destination context. | A discovery token is short-lived, opaque, and not copy authority. |
| Copy exact revision | `project:create` or destination setup authority, `template:copy-out` for the exact source revision, and `template:manage` for the destination; recheck rights/compatibility and both project states. | Failure of any one check denies that item without revealing unauthorized metadata. |
| Place/build copied template | Current destination membership plus the normal authoring/build capability and access to the destination snapshot. | Source access is neither required nor accepted as a substitute. |

Service identities receive the minimum capability for validation or byte
materialization. The browser never receives raw object locators or permission
claims it can replay. The local agent receives a bounded, expiring job grant for
one already-authorized package revision and reports the exact digest it read.

Authorization changes take effect on the next request and before final copy
commit. A list result or preflight is evidence, not a lease on permission.

## 7. New-project administrator flow

### 7.1 Ordered flow

1. **Start project setup.** Verify `project:create`; create only an expiring
   setup intent, not a generally visible project library.
2. **Choose template mode.** Default to **None**. The administrator may choose
   None, selected eligible revisions, or All eligible revisions.
3. **Discover candidates.** Group only authorized candidates by source project
   or approved registry collection. Show project-local name, exact revision
   label and digest abbreviation, compatibility, rights/copy eligibility, and
   update/retirement state. Invalid, quarantined, or unauthorized packages are
   absent; a formerly selected inaccessible item becomes a nonrevealing error.
4. **Freeze the selection.** Resolve every choice to exact revision IDs and
   digests. **All** means all eligible revisions in this frozen candidate set,
   not future additions and not an unbounded live query.
5. **Preflight.** Recheck source/destination authority, current package state,
   byte reachability/hash, rights, compatibility, destination name/lineage
   collisions, and idempotency history. Return one result per exact choice.
6. **Resolve findings.** Exact duplicates become visible idempotent `Already in
   destination` results. Any unavailable, incompatible, unauthorized, missing,
   or conflicting choice blocks commit. The administrator may go back, remove
   it explicitly, choose None, or cancel setup. VERA never silently excludes or
   substitutes a revision.
7. **Review.** Show the exact frozen set, source-to-destination names, revisions,
   digests, and any deliberate exclusions. Recheck the count for **All**.
8. **Commit atomically.** Reauthorize and create the project plus every selected
   project-owned snapshot under one idempotency key. Either the declared set is
   committed or no new project/library becomes active.
9. **Report.** Return the destination project ID, each created or idempotently
   reused revision, exact digest, source evidence, and an audit event. A retry
   with the same key returns the same logical result.

An implementation may persist a private setup draft for recovery, but it must
not expose a half-created destination or partially copied library. If product
requirements later demand “create project now and repair templates later,” that
is a separate Producer decision with explicit partial-state semantics.

### 7.2 Duplicate and conflict rules

| Destination condition | Result |
| --- | --- |
| Same package digest already belongs to the same project template lineage | Idempotent `already present`; do not create another revision or advance a pointer. |
| Same lineage, different exact package revision | Present as `different revision`; require explicit add/update intent outside implicit duplicate handling. |
| Same display name, different lineage | `name conflict`; require explicit destination rename or deselection before commit. Never overwrite. |
| Same digest under a different destination item | Report a content duplicate and require an explicit merge/reuse decision in a later library-management flow; project creation does not guess. |
| Source current pointer changed after selection | `stale selection`; refresh and reconfirm the exact set. Never follow the pointer silently. |

## 8. Producer-reviewable scenarios

These scenarios describe expected behavior and retained evidence; they do not
execute production actions in issue #19.

### S19-01 — external intake succeeds

**Given** an authorized intake operator supplies a ZIP with one manifest, exact
declared bytes, complete provenance/rights, and a supported validator profile,
**when** structural, format, compatibility, and rights checks pass, **then** VERA
records one immutable registered revision keyed by the package digest. It is not
available to any project until an authorized attachment/copy occurs.

Evidence: package digest, canonical manifest, validation receipt/ruleset,
provenance attestation, rights decision, actor, and registration event.

### S19-02 — one-project use remains pinned

**Given** project A has an attached revision R1, **when** an Editor places it and
the publisher later registers R2, **then** the use, checkpoint, and prior build
remain pinned to A/R1 and their resolved snapshot hash. R2 appears only as an
available update for a later explicit migration.

Evidence: project ownership, R1 package digest, use pin, resolved snapshot hash,
R2 registration, unchanged checkpoint/build dependency lists.

### S19-03 — selected templates copy to a new project

**Given** an administrator may create project B and copy R1 and Q3 from
authorized project A, **when** both exact revisions pass preflight, **then** one
atomic commit creates B-owned snapshots of R1 and Q3. Removing the actor from A
afterward does not remove B's snapshots or grant B access to any other A data.

Evidence: frozen two-item selection, source and destination authorization
decisions, copy events, B-owned revision IDs, exact source digests.

### S19-04 — All is a frozen eligible set

**Given** five discoverable candidates but only four are currently eligible,
**when** the administrator chooses All, **then** the review identifies the four
exact revisions and explains the excluded candidate before commit. A sixth
template registered later is not added. If one of the four becomes ineligible
before commit, the entire commit stops for reconfirmation.

Evidence: candidate-set version, four exact digests, exclusion reason safe to
show, final preflight, committed count.

### S19-05 — duplicate detection never overwrites

**Given** destination B already contains R1, plus a different lineage using the
same display name as Q3, **when** both are selected again, **then** R1 reports
`already present` and Q3 reports `name conflict`. VERA neither creates a second
R1 nor overwrites, renames, merges, advances, or substitutes Q3 automatically.

Evidence: destination collision keys and per-choice results with zero mutation.

### S19-06 — missing or invalid package stays unavailable

**Given** a package omits a declared font or contains a traversal path, **when**
intake runs, **then** it is quarantined with a stable safe diagnostic and never
appears in project selectors. Supplying corrected bytes is a new candidate and
cannot inherit the failed candidate's approval.

Evidence: failure stage/code, safe manifest pointer/path, validator version,
quarantine event, no project attachment.

### S19-07 — unauthorized cross-project copy reveals no access

**Given** an actor saw a template name previously but lacks `template:copy-out`
for project A or `template:manage` for B, **when** they replay a selection or
copy command, **then** VERA rechecks both boundaries, creates nothing, issues no
byte locator, and returns a nonrevealing access/stale-choice result. Membership
in either project does not imply membership in the other.

Evidence: denied authorization decision, audit event without private package
metadata, unchanged destination library.

## 9. Failure and retry matrix

| Failure point | Visible result | Retry rule | Mutation |
| --- | --- | --- | --- |
| Archive/manifest invalid | Quarantined with stable content finding. | Corrected content is a new candidate/digest. | No registry or project mutation. |
| Validator service unavailable | Intake pending/failed with infrastructure reason. | Same staged digest may retry idempotently. | No registration. |
| Declared bytes missing at copy | Exact choice unavailable; whole setup commit blocked. | Restore and hash-verify same digest, or explicitly deselect. | No active destination. |
| Target incompatible | Exact choice incompatible with named reason. | Select another exact revision explicitly or change destination policy outside this attempt. | No substitution. |
| Authorization changes after preflight | Nonrevealing denial/stale setup. | Refresh authorization and candidate set. | No partial commit. |
| Exact duplicate | `Already present` with retained destination revision ID. | Same idempotency key returns same result. | No duplicate row. |
| Name/lineage conflict | Conflict requiring explicit rename/deselection. | New reviewed setup intent. | No overwrite or merge. |
| Commit response lost | Outcome unknown to client. | Retry same idempotency key; server returns same atomic result. | At most one logical project/copy set. |

## 10. Implementation boundaries and proposed follow-ups

Issue #19 approves none of the contracts or code below. Each contract change
must state what changes, why, compatibility impact, generated outputs, and
acceptance changes before implementation.

### 10.1 Template registration slice

Owns:

- external package-manifest and validation-receipt schemas;
- safe directory/ZIP staging, canonical digest, quarantine, format-validator
  plugin boundary, provenance/rights evidence, registered revision lifecycle,
  content-addressed storage, and failure reports;
- registry capabilities and audited commands.

Does not own native template design/conversion, project creation, authoring
placement, compiler events, or Resolve execution. Each native format validator
may require its own capability and Producer acceptance slice.

### 10.2 Project library and project-creation slice

Owns:

- project-template item/revision/lifecycle schemas reconciled with Phase 9;
- exact-revision candidate queries and capability checks;
- setup intent, frozen None/Some/All selection, preflight results, atomic copy,
  idempotency, duplicate/conflict semantics, and audit evidence;
- project-owned availability, retirement, supersession, and explicit update
  commands.

Project-library persistence and project creation may be separate implementation
slices if their contracts are approved together and dependency order is
explicit. Neither may use a governed live source reference in place of the
accepted snapshot decision.

### 10.3 Compiler and Resolve placement slices

Own:

- the separately approved `TemplateUse` / `GraphicUse` contract additions,
  exact revision and resolved snapshot projection into build dependencies,
  deterministic compiler events and goldens;
- format-specific materialization, semantic-input verification, Free fallback,
  Studio placement, save/reopen evidence, and honest failures.

They consume only an already-authorized project snapshot. They do not discover
source projects, follow current pointers, repair packages, or broaden rights.
The existing curated Fusion plan remains the specific authority for its lower-
third capability and later GF-1/GF-2 work.

### 10.4 Authoring and administration UI slices

Own:

- accessible intake/review surfaces for authorized roles;
- project-library list, revision/update/retired/held states;
- the new-project None/Some/All flow, exact-revision review, per-choice findings,
  atomic result, and recovery states;
- authoring picker and semantic forms for already available project templates.

The UI must conform to the accepted issue #13 design contract: role-invalid
actions are absent from the DOM, project and product switching remain distinct,
status is not color-only, and local-agent/Resolve labels are capabilities rather
than authorization. High-fidelity browser work remains separately bounded.

### 10.5 Contract-change inventory

At least these proposed boundaries require explicit later approval:

1. `ExternalTemplatePackageManifest` and canonicalization/hash rules.
2. `TemplateValidationReceipt`, quarantine findings, provenance, and rights
   evidence.
3. Phase 9 project-template item/revision/lifecycle reconciliation.
4. Exact-revision project-copy command, frozen selection, per-item preflight,
   idempotency, and audit events.
5. Authoring-use and compiler/build dependency projection.
6. Format-specific package payload and placement contracts.

No `/contracts` file or generated type changes in issue #19.

## 11. Acceptance mapping and Producer checklist

### 11.1 Issue acceptance mapping

| Issue #19 criterion | Design evidence |
| --- | --- |
| Intake forms, manifest/provenance, revision identity, validation/quarantine, licensing, failures | Sections 2 and 3 |
| Project ownership, local availability, immutable references, removal/supersession, reproducibility | Section 4 |
| None/Some/All creation flow and unavailable/incompatible/duplicate reporting | Sections 7 and 9 |
| Intake, project administration, creation, and cross-project authorization | Section 6 |
| Seven Producer-reviewable scenarios | Section 8 |
| Registration, creation, compiler/placement, UI, and contract follow-ups | Section 10 |
| Producer approval before implementation | Checklist below and issue remains `In review` |

### 11.2 Producer acceptance steps

Automated repository and scope evidence is supplied in the issue handoff. The
Producer should perform these judgment checks:

1. Open `docs/investigations/issue-19-external-template-intake.md` and read the
   one-sentence decision plus section 5.
   **Expected:** copying creates a destination-owned immutable snapshot; byte
   deduplication is allowed, but source permissions, lifecycle, and future
   revisions are not inherited. Confirm this resolves the issue's open choice.
2. Review sections 2 and 3.
   **Expected:** only a directory or non-self-extracting ZIP with a complete
   manifest enters staging; exact bytes and rights are declared; unsupported or
   invalid packages remain quarantined; VERA never designs, converts, repairs,
   or executes the package during intake.
3. Review section 4.
   **Expected:** registered revisions and project-owned revisions are distinct;
   uses pin exact revisions; supersession, retirement, withdrawal, and holds
   never silently rewrite or erase prior use/build evidence.
4. Review section 6.
   **Expected:** capabilities separate intake, registration, discovery,
   project creation, project management, and copy; every source/destination
   boundary is rechecked; visible names and stale tokens grant nothing.
5. Walk section 7 in order for None, selected revisions, and All.
   **Expected:** None is the default; All freezes an exact eligible set; every
   selected revision is preflighted; conflicts block the atomic commit; no
   partial library, silent exclusion, pointer following, or revision
   substitution occurs.
6. Review scenarios S19-01 through S19-07 in section 8.
   **Expected:** intake, one-project use, selected copy, All, duplicate,
   missing/invalid, and unauthorized access each have an observable result and
   retained evidence that a later implementation can test.
7. Review section 10.
   **Expected:** registration, project library/creation, compiler/placement,
   and authoring/admin UI have separate ownership; every production contract is
   an explicit follow-up; no production code may begin from this design alone.
8. Record exactly one response on issue #19:
   - acceptance: `Accept issue #19 external template intake and project-scoped reuse design, including the project-local immutable snapshot decision and the implementation boundaries in section 10.`
   - failure: `Issue #19 acceptance failed at checklist step <number>: <observed mismatch or requested decision change>.`

Leave issue #19 `In review` until the Producer records the acceptance response.
Never infer acceptance from silence, mark it `Done` from an agent self-report,
or start a follow-up implementation before acceptance.
