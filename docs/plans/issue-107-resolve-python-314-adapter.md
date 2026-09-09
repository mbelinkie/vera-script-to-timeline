# Issue 107 — Split Resolve Python 3.14 adapter from package verification

## Bounded scope

Retain the successful restricted injected-object evidence from issue 6 and
make the staged Workflow Integration startup importable by Resolve's embedded
Python 3.14 without loading VERA's Python 3.12 native extensions. Package
verification remains an external locked-runtime step. Its successful counts,
interpreter identity, exact package path, fresh project name, timestamp, and
file inventory are written to a standard-library JSON attestation. Resolve
re-hashes that inventory before it constructs the injected adapter.

## Exclusions

- No frozen contract, generated type, fixture, golden file, or accepted test
  changes.
- No change to the external Studio adapter's verification or connection
  behavior.
- No production project reuse, deletion, overwrite, rendering, upload, or
  research-project data.
- No installer, product UI, cryptographic signing service, or long-lived
  attestation format commitment.

## Contracts, fixtures, and dependencies

The existing `TimelineManifest v1`, `BuildReport v1`, Slice 0.2 package, and
producer-authored Text+ asset are consumed unchanged. The attestation is a
staging-only request/evidence format, not a frozen product contract. No
dependency is added: the injected path uses only Python 3.14 standard-library
modules and the existing Resolve/Fusion API objects. The external verifier
continues using the exact locked Python 3.12 environment.

## Automated checks

- Import the injected startup with `python -S` and prove OTIO, jsonschema, and
  referencing are absent.
- Prove a full external verification pass creates counts, interpreter identity,
  a fresh project name, and a complete hash/size inventory.
- Prove any package-byte change stops before Resolve adapter construction.
- Preserve exact preflight, mutation, save/reopen, verification, and partial
  unique-project reporting behavior with strict doubles.
- Run focused pytest, Ruff, strict mypy, full `npm run validate`, a frozen-file
  audit, and final diff review.

## External acceptance

1. Generate a fresh accepted Slice 0.2 package and an attestation naming a new
   `VERA Issue 107 Acceptance <timestamp>` project.
2. Install the staged wrapper and config without any `.venv` or
   `site-packages` path.
3. In Resolve, set **External scripting using** to **None**, leave automatic
   safe scripted actions allowed, restart, and open a disposable project with
   a timeline on the Edit page.
4. Launch **Workspace > Workflow Integrations > VERA Workflow Integration**.
5. Retain the attestation and result JSON. Expected: the result reports
   `startup_verified`, Resolve's exact version/build, the fresh project name,
   and package-verification evidence; the named project and its empty
   manifest-configured timeline were saved, reopened, and identity/settings
   verified. No media, event, Text+, or render capability is claimed. Any
   failure is retained without weakening the restricted setting.
