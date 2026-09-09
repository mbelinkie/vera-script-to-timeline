# Issue 6 — Resolve-launched Python Workflow Integration adapter

## Scope and boundary

This is a staged investigation of whether a Resolve-launched Python Workflow
Integration receives an injected API object without loading the external
`DaVinciResolveScript` bridge. It does not package or install a companion,
alter frozen contracts or fixtures, or change the existing external Studio
adapter.

The repository-owned staging artifact is
`staging/resolve-workflow-integration/VERA Workflow Integration.py`. Resolve is
expected to inject its `resolve` object when it launches the script. The current
stage is deliberately a standard-library-only, non-mutating probe: it reads
`GetProductName()` and `GetVersion()` and retains a JSON result. It makes no
project, timeline, or media changes.

## Automated evidence

`tests/test_studio_spike.py` covers the proposed injected delivery path with
strict doubles: it cannot invoke the external bridge, discovery failure stops
before project creation, assembly retains the accepted adapter order, and a
post-creation failure reports its exact partial project. These are adapter
evidence only. They do not establish a real Resolve capability or Python
runtime compatibility.

## Version-stamped findings

| Finding | Version / evidence | Status |
| --- | --- | --- |
| Existing external path works through the documented bridge. | Producer-accepted Studio 21.0.4, API build 5, 2026-08-25; retained in `CAPABILITIES.md`. | Historical baseline only. |
| Resolve launched the registered script. | `vera-workflow-integration-started.txt`, 2026-09-09. | Proven. |
| The prior wrapper can locate its own file with `__file__`. | Resolve log, 2026-09-09: `NameError: name '__file__' is not defined`. | Disproved; corrected in the probe. |
| The existing Python 3.12 dependency set can load inside Resolve. | Resolve log, 2026-09-09: embedded Python 3.14.7; checkout has Python 3.12 native extensions. | Disproved; full adapter is not run in this stage. |
| Resolve supplies an injected object when external connection access is restricted. | Producer-run probe, 2026-09-09: `DaVinci Resolve Studio`, version `[21, 1, 0, 14, ""]`, `status: "injected_probe_passed"`. | Proven for the narrow injection boundary. |

**Current recommendation: revise, not retain.** The 2026-09-09 probe proved
that Resolve provides its injected object with external scripting set to
`None`; it therefore removes the external *connection setup* boundary for a
compatible in-process integration. But its embedded Python 3.14 cannot import
the checkout's Python 3.12 native packages, so the staged full adapter cannot
create the accepted timeline. A later bounded slice must design a compatible
runtime boundary before any in-process delivery is reconsidered.

## Producer external-acceptance procedure

1. Set Resolve's **External scripting using** preference to **None** and leave
   **Automatic scripted actions** at **Allow safe**, then restart Resolve.
2. Launch **Workspace > Workflow Integrations > VERA Workflow Integration**.
   This probe does not need an open project and makes no changes.
3. Read `vera-workflow-integration-result.json` in Resolve's `Workflow
   Integration Plugins` directory. Expected: `status: "injected_probe_passed"`
   plus product name and version.
4. Record that JSON, the exact Resolve version/build, and the restricted
   preference in the issue. If it reports `workflow_launcher_failed`, retain
   that JSON and the Resolve log; do not retry by enabling external scripting.

The producer-run probe is retained External evidence for the injection
boundary. Keep the issue `In review` and do not add a capability claim to
`CAPABILITIES.md`: a passing probe establishes only the injected-object
boundary, not an executable VERA delivery adapter.
