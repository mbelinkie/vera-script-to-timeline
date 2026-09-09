# Issue 6 — Resolve-launched Python Workflow Integration adapter

## Scope and boundary

This is a staged investigation of whether a Resolve-launched Python Workflow
Integration can reuse VERA's existing supported public adapter without loading
the external `DaVinciResolveScript` bridge. It does not package or install a
companion, alter frozen contracts or fixtures, or change the existing external
Studio adapter.

The repository-owned staging artifact is
`staging/resolve-workflow-integration/VERA Workflow Integration.py`. Resolve is
expected to inject its `resolve` object when it launches the script. The wrapper
loads `vera_timeline_agent.workflow_integration`, whose sole action is to pass
that object to `run_injected_delivery`. The injected path retains package
verification; current-project/current-timeline discovery; a unique-name check
before mutation; exact assembly; save/close/reopen verification; and explicit
partial-project reporting.

## Automated evidence

`tests/test_studio_spike.py` covers the injected path with strict doubles:

- it cannot invoke the external bridge and its staged source contains neither
  bridge import nor bridge call;
- discovery/pre-mutation failure stops after the current-context probe and
  before creating a project;
- a build keeps the accepted adapter order, record frames, exact Text+
  placement, marker addition, and save/reopen verification; and
- a failure after the unique project is created reports that exact partial
  project rather than presenting a safe stop.

These are adapter evidence only. They do not establish any real Resolve
capability.

## Version-stamped findings

| Finding | Version / evidence | Status |
| --- | --- | --- |
| Existing external path works through the documented bridge. | Producer-accepted Studio 21.0.4, API build 5, 2026-08-25; retained in `CAPABILITIES.md`. | Historical baseline only. |
| The staged path does not load the bridge and instead accepts a supplied `resolve` object. | Repository tests on 2026-09-09. | Proven only with doubles. |
| Resolve supplies that object to this stage when external connection access is restricted. | No real test yet. | Pending External acceptance. |

**Current recommendation: revise, not retain.** The code is a credible narrow
test harness, but it has not yet shown that a real Resolve Workflow Integration
gets an injected object independent of external scripting. If the restricted
producer run verifies the build and reopen checks, the companion genuinely
removes the external *connection setup* boundary for this launch path. It does
not create a new editing API or remove Studio/API availability requirements. If
the injected object is absent or unusable when access is restricted, it is only
a nicer launcher and should be abandoned rather than productized.

## Producer external-acceptance procedure

1. In a disposable acceptance project, confirm Resolve Studio's exact About
   version and API build. Restrict external scripting/connection access in the
   relevant Resolve preference, then restart Resolve if it requires a restart.
2. Regenerate the accepted package using the documented Slice 0.2 command.
   Copy `VERA Workflow Integration.py` and a new
   `vera-workflow-integration.json` beside it through Resolve's own Workflow
   Integration Scripts process. Set absolute `repositoryPythonPath` and
   `packageDir`; choose a never-before-used `projectName`.
3. Open the disposable project on the Edit page and launch the integration from
   **Workspace > Workflow Integrations**. Expected: JSON identifies that exact
   Resolve version/build and returns `verified`; a new uniquely named project
   is created, saved, closed, reopened, and verified.
4. Inspect the retained project: the accepted media, tracks, Text+ placement,
   markers, and timeline match the existing accepted test timeline. Expected:
   no reported discrepancy. A visual editorial judgment remains: confirm the
   observed timeline is the intended accepted test timeline.
5. Paste the JSON result, exact Resolve version/build, whether restricted
   external access was active, and `Accept Issue 6: retain` or `Reject Issue 6:
   abandon` into the issue. If it fails after project creation, preserve and
   name the partial project; do not overwrite or delete it.

The producer's response is the required External evidence. Until then, keep
the issue `In review`; do not add a capability claim to `CAPABILITIES.md`.
