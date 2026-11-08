# #489 — Resolve 21.1.1.10 static binary / bundled MCP loophole audit

**2026-11-08 — static-only follow-up to #477; no native capability proved.**
This is a *bounded subset inventory*, not a full-app negative scan. The code
was developed in a Linux Zodex container; after confirming availability, a
read-only **Mac Bridge** separately inspected selected actual installed
21.1.1.10 files. Several newer-method-name strings, including exact
`MoveItems` and `SetPosition` tokens, **are present in the main executable**
despite being absent from the installed SDK declarations. No string alone
proves a supported/callable method or UID-preserving operation. No Resolve
process, MCP server, SDK, or production project was started, loaded, connected
or mutated.

## Scope and evidence ledger

| Claim / source | Evidence class and exact scope | Finding / limit |
| --- | --- | --- |
| Installed app identity | **Fresh Mac Bridge metadata/hash**, corroborating [#477](issue-477-native-roll-feasibility.md#acquisition-identity-and-evidence-classes); `Contents/Info.plist` SHA-256 `7539507115e554d8b936253934c394d9ded2b8f509eb5edd1cb58b047391a2f4` | `CFBundleShortVersionString=21.1.1`, `CFBundleVersion=21.1.10010`. Same as #477; no running-app/Studio edition handshake. |
| Installed SDK stub | **Fresh Mac Bridge hash**, corroborating [#477 I1](issue-477-native-roll-feasibility.md#source-ledger--official-installed-files); `DaVinciResolveScript.pyi`, SHA-256 `2755259ef5f57b5d477786f799892e5b86ed3945db84bf88fb69bf751b36e651` | Same bytes as #477; its 2,848-line stub does not declare `SetLeftOffset`, `SetRightOffset`, `SetPosition`, `GetPosition`, `MoveItems`. |
| Installed SDK README | **Fresh Mac Bridge hash**, corroborating [#477 I2](issue-477-native-roll-feasibility.md#source-ledger--official-installed-files); `README.md`, SHA-256 `5f58c94da8ec3c1f390d77ad9c60675263591dc101159b302e50b5774513830b` | Same bytes as #477; 628 lines, last updated 2026-08-31. |
| Installed SDK changelog | **Fresh Mac Bridge hash**, corroborating [#477 I3](issue-477-native-roll-feasibility.md#source-ledger--official-installed-files); `CHANGELOG.md`, SHA-256 `b12c961176d79a5fc87757a21dc7ce2e147f13fb4dab927ed9154943c7de1491` | Same bytes as #477; 132 lines, last updated 2026-09-01, newest section 21.1. |
| New bounded scanner | **Synthetic-only tests**, `python/vera_timeline_agent/issue489_static_resolve_audit.py`, `tests/test_issue489_static_resolve_audit.py` | 55 focused tests including #477 passed before final ceiling adjustment. Mac Bridge supplied a separately bounded streamed-byte inspection, not an invocation of the newly authored scanner (not installed in the Mac checkout). |
| 21.1.2/21.2 signatures | **Published secondary**, [#477 version table](issue-477-native-roll-feasibility.md#version-comparison--published-documentation-is-not-an-installed-sdk) | Setters and movement methods are *new in 21.1.2* in the published mirror, but neither their existence there nor string presence in an installed binary would prove a supported 21.1.1 roll. |
| Installed main binary | **Fresh Mac Bridge file/hash/read-only streamed bytes**, Mach-O universal x86_64/arm64, 1,049,754,864 bytes, SHA-256 `d14f64e789f214fbfccbd9cad54b2e61b90d4bd202a9eb0105a74011306cbea5` | Exact-token `MoveItems` and `SetPosition` found; raw substrings `GetPosition`, `RollEdit` also found. `AddTake`, `FinalizeTake`, `GetSmartReframeStatus` positive; raw `SetLeftOffset`, `SetRightOffset`, `RippleTrim` absent in the scanned main executable. Some full regular-expression boundary scans timed out at the Bridge's 35-second cap; **binary names are present-but-unsupported, not an API or callable guarantee**. No dylib/.so-wide coverage. |
| Installed Blackmagic `ResolveMCP` helper | **Fresh Mac Bridge file, hash, signing metadata**, 430,432-byte Mach-O universal x86_64/arm64, SHA-256 `0e7a874ccf91f59a9816b2414a80859ff7ff1056528a4c9ed5eb17e0affccf67`; Apple code signature `com.blackmagic-design.resolve.mcp`, Team `9ZGFBWLSYP` | No target method substrings from helper's `strings -a` output. This is a binary string check, not complete code-level proof. No helper executed. |
| Installed Blackmagic MCP package | **Fresh Mac Bridge archive/hash/manifest**, `Contents/Resources/DaVinciResolve.mcpb`, SHA-256 `2d92e52a9b09918f09d9ae803e83640cef0e856c5b5f8332ff73fa31f92baddf` | Manifest v0.3, package v1.0 declares 14 tools: general scripting helpers, status, DCTL/LUT manipulation; **no dedicated vendor roll/trim tool declared**. MCP `run_script` / `run_script_unsafe` exists but has no standalone supported in-place roll semantics. No MCP process started or tools/list invoked. |
| Installed official SDK `Examples/` | **Fresh Mac Bridge path enumeration plus grep**, 21 publicly bundled `.py`/`.lua` files | Read-only `grep -RnlE 'AddTake|FinalizeTake|recordFrame|Offset'` returned no matches. `rg` unavailable on host, so grep was used. This is a bounded negative *for those literal terms in those Examples*, not universal absence of roll guidance. |
| Community issue #336 | **Public third-party discussion**, [complete issue and comments](https://github.com/samuelgursky/davinci-resolve-mcp/issues/336), checked 2026-11-08 | Corrected fixture error documented below; observations are Windows Studio 21.1.2.10, not native VERA or installed 21.1.1 evidence. |

The paths behind #477's four previously measured hashes were:

```text
/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Info.plist
/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/DaVinciResolveScript.pyi
/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/README.md
/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/CHANGELOG.md
```

The four hashes above matched the earlier #477 evidence **again** through
the read-only Mac Bridge on 2026-11-08. A third-party
[21.1 native-MCP inspection](https://github.com/ismael-joffroy-chandoutis/comfyui-cinema-pipeline/blob/main/docs/12-davinci-resolve-native-mcp.md)
describes `Contents/Applications/ResolveMCP` and
`Contents/Resources/DaVinciResolve.mcpb` in a **different** 21.1.0 host. The
real 21.1.1.10 host now independently confirms those files and their
metadata/manifest; that earlier report did not authenticate this build.
Similarly, [the community `davinci-resolve-mcp` repository](https://github.com/samuelgursky/davinci-resolve-mcp)
and its issue #336 are **not** Blackmagic's bundled ResolveMCP.

## Reconciliation of #336 (full public comment history)

The [original 2026-11-01 reporter account](https://github.com/samuelgursky/davinci-resolve-mcp/issues/336)
claimed several broken methods on Windows Studio 21.1.2.10. Subsequent
comments **change the conclusion**:

1. **2026-11-02 correction 1:** `Timeline.ExportFrame` works for **relative**
   `frameOffset` values `0 ... EndFrame - StartFrame - 1`; the initial test
   passed absolute frames or targeted a zero-duration timeline. The marker
   issue is `TimelineItem.AddMarker(0)` (true/no marker), **not**
   `Timeline.AddMarker(0)` (works); `MediaPool.AddToPhotoAlbum` still had
   negative readback. [Reporter correction](https://github.com/samuelgursky/davinci-resolve-mcp/issues/336#issuecomment-6578351465).
2. **2026-11-02 correction 2 (malformed fixture):** `AppendToTimeline`'s
   `recordFrame` is an **absolute** timeline coordinate. Values 0/200/400 on a
   timeline starting at 86400 put clips *before* `StartFrame`; `EndFrame`
   remained equal to `StartFrame`. With correctly anchored clips at 86400,
   86600, 86800, `Timeline.DeleteGaps()` closed gaps. **Withdraw** the
   `DeleteGaps` failure and avoid inferring behavior from malformed geometry.
   [Reporter correction](https://github.com/samuelgursky/davinci-resolve-mcp/issues/336#issuecomment-6578453855).
3. **2026-11-02 maintainer response:** ledger corrections landed in v4.18.5;
   `recordFrame` below start had already been refused by the *community MCP
   wrapper*, not necessarily Resolve itself. The remaining reports were
   `AddToPhotoAlbum`, `SetPosition` / `MoveItems`, `SetLeftOffset`, and
   `TimelineItem.AddMarker(0)`. [Maintainer reply](https://github.com/samuelgursky/davinci-resolve-mcp/issues/336#issuecomment-6582073984).
4. **2026-11-06 maintainer request:** explicitly requested retesting the
   surviving failures on a **well-formed** timeline because the bad source
   geometry may also have invalidated the `SetPosition` / `MoveItems` results.
   The destructive `SetLeftOffset` result was **not re-run** and was measured
   with the malformed fixture. No later independent correction/retest appears
   in the checked public thread as of 2026-11-08.
   [Maintainer retest request](https://github.com/samuelgursky/davinci-resolve-mcp/issues/336#issuecomment-6683747042).

Therefore #336 neither demonstrates a viable same-UID roll nor demonstrates
that an edit setter fails on a correctly formed 21.1.1.10 Mac timeline. Do not
run this or any other destructive experiment under #489.

## Bounded offline scanner and its interpretation

The new `python/vera_timeline_agent/issue489_static_resolve_audit.py` is a
read-only *data* reader for **explicit relative candidates only**, not an
automatic filesystem search. It verifies regular files and NOFOLLOW path
components, fails on symlinks, hardlinks/repeated files, oversized files,
changed files or file-count/aggregate limits (48 files; 1,200 MiB per binary,
2 MiB per resource; 1,600 MiB combined), and writes no output files. The
binary ceiling was deliberately raised from the phase-1 512 MiB value only
after reading the installed 1,049,754,864-byte executable's metadata. It records
SHA-256, byte count, Mach-O magic, exact method tokens, and strictly filtered
candidate MCP edit-tool names; no neighboring strings or config values are
printed. It **does not** import the SDK, execute Mach-O/dylib/`.so`, use
`ctypes`, connect to Resolve, or invoke a built-in MCP tool.

Positive controls: `AddTake`, `FinalizeTake`, `GetSmartReframeStatus`.
21.1.2+ and bounded hypothetical candidates: `SetLeftOffset`,
`SetRightOffset`, `SetPosition`, `GetPosition`, `MoveItems`, `RollEdit`,
`RippleTrim`. Impossible control:
`VERA489_IMPOSSIBLE_NATIVE_METHOD_9d1297b1`. All presence findings are
**string inventories only**. Output states apply solely to the supplied
subset: `absent` (controls found, no candidates),
`present-but-unsupported` (candidate string found, no API guarantee), or
`INCONCLUSIVE` (unexpected magic/impossible control/missing controls/error).
No state gives full-app coverage, native proof, edit authorization or clearance
for #473/#312. An MCP edit-tool *hint* requires independent review and a
stop before any use; absence of a JSON-shaped hint cannot rule out registered
native tools inside compiled code.

## Mac Bridge static checks — performed and reproducible

The commands below **were run** through the read-only Mac Bridge on
2026-11-08 with `approval_mode=auto` (no trust enable requested). Bridge v0.5.0
limits one command to 240 characters and 35 seconds. Output was limited to
metadata, hashes, method *names*, and safe SDK examples. No environment,
credentials, configuration or media was read. The MCP helper was **not**
executed, including no `tools/list`; Resolve was never launched.

**1 — Revalidate identity.** These exact hashes **matched** historical #477;
the four full SHA-256 values and version result are in the evidence table.

```sh
plutil -p '/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Info.plist' | grep CFBundle
shasum -a 256 '/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Info.plist'
shasum -a 256 '/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/DaVinciResolveScript.pyi'
shasum -a 256 '/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/README.md'
shasum -a 256 '/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/CHANGELOG.md'
```

**2 — Confirm candidate paths and signatures without loading.** All commands
below were executed read-only and returned hashes, signature and archive
contents described in the table. The two binaries were identified via `file`
as universal Mach-O with x86_64 and arm64 slices. The MCP `.mcpb` archive
listed `LICENSE`, `icon.png`, `manifest.json`, `package.json` and
`server/index.js`. Nothing was extracted to disk or run.

```sh
ls -l '/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Applications/ResolveMCP'
file '/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Applications/ResolveMCP'
shasum -a 256 '/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Applications/ResolveMCP'
codesign -dv --verbose=2 '/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Applications/ResolveMCP' 2>&1 | grep -E 'Identifier|TeamIdentifier|Authority|Format'
shasum -a 256 '/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Resources/DaVinciResolve.mcpb'
unzip -Z -1 '/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Resources/DaVinciResolve.mcpb' | head -n 48
```

**3 — Main executable token sweep.** The Python `issue489_static_resolve_audit`
CLI was **not run against the installed Mac executable**: it exists only in
this isolated Zodex worktree. Instead, the Mac Bridge ran a read-only bounded
Python streamed-byte search of the real Mach-O executable, one 1 MiB chunk
at a time, across its full length, checking each adjacent chunk pair to avoid
false negatives from split names; no code was loaded. First it verified all
three positive controls `AddTake`, `FinalizeTake`,
`GetSmartReframeStatus` were present. Next it returned the following
raw-name inventory (exact word-boundary separately confirmed for `MoveItems`
and `SetPosition`):

| Probe | Raw substring in main binary | Meaning |
| --- | --- | --- |
| `AddTake`, `FinalizeTake`, `GetSmartReframeStatus` | all **present** | Controls found, as expected |
| `SetLeftOffset`, `SetRightOffset` | **absent** | Specific byte strings absent in this file; no claim about all libraries or runtime dispatch |
| `MoveItems`, `SetPosition` | **present**, exact-token verified | Newer names are compiled into 21.1.1.10 executable despite missing SDK declarations. **Not proof of exposed API** |
| `GetPosition`, `RollEdit` | **present** as raw substrings | Exact semantics unknown, potentially internal/editor code |
| `RippleTrim` | **absent** | No support inference |
| Impossible-name negative | **not verified in full stream** | A full probe request exceeded the Bridge's command-length limit; no absence claimed |

The Bridge returned a local internal error for a full-executable `strings`
pipeline. A memory mapping attempt was denied by the host OS
(`PermissionError`), so the code used regular bounded reads. A few more
costly *exact-boundary* regex passes timed out after 35 seconds; no results
from timed-out calls were counted as matches or nonmatches. **Do not treat
this ad hoc scanner as equivalent to a full exact-token, symlink-safe #489
scanner run on all installed libraries.** Overall main-binary subset verdict
is **present-but-unsupported**.

For completeness, the actual signed `ResolveMCP` helper's read-only
`strings -a` scan had no matches for `AddTake`, `FinalizeTake`,
`GetSmartReframeStatus`, `SetLeftOffset`, `SetRightOffset`,
`MoveItems`, `RollEdit` or `RippleTrim`; no inference about internal
registration is possible from this alone. The official `.mcpb`
`manifest.json` declared:

```text
launch_resolve, get_resolve_status, get_whats_new, get_scripting_api,
search_scripting_api, run_script, run_script_unsafe, get_scripting_docs,
list_dctls, list_luts, update_dctl, delete_dctl, delete_lut, generate_lut
```

**No named vendor-supported trim or roll tool is declared.** Generic
`run_script` is merely a route to whatever the SDK already supports; it
cannot be presumed a special roll primitive. No MCP action was called.

**Optional reproducible Mac full scanner invocation, NOT EXECUTED** until
the new #489 module is present in a reviewed Mac checkout:

```sh
uv run --frozen python -m vera_timeline_agent.issue489_static_resolve_audit --app '/Applications/DaVinci Resolve/DaVinci Resolve.app' --binary Contents/MacOS/Resolve --binary Contents/Applications/ResolveMCP
```

Additional binary/library candidates would need explicit, reviewed paths;
none were exhaustively searched. If a candidate fails scanner validation,
record `INCONCLUSIVE`; do not remove guards or widen limits. If a named
vendor-supported native trim/roll tool is ever found, **STOP** for independent
review. Never call it as part of this ticket.

**4 — Official installed Examples sweep.** The public SDK Examples directory
was enumerated read-only (21 bundled `.py`/`.lua` examples). The first
`rg` command failed because ripgrep is unavailable on the host. It was
repeated with installed `grep` over the same public directory; **no matches**
for `AddTake`, `FinalizeTake`, `recordFrame` or `Offset` appeared.

```sh
find '/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Examples' -type f -name '*.py' | head -n 48
grep -RnlE 'AddTake|FinalizeTake|recordFrame|Offset' '/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Examples'
```

The no-match finding applies only to these exact strings in public Examples,
not to every possible vendor in-place trim mechanism.

## Disposition / acceptance impact

**Installed #489 static loophole outcome: main-binary subset
present-but-unsupported; bundled MCP manifest exposes no dedicated
vendor-supported trim/roll tool; no Examples matches on targeted strings.**
There are important, newly found method-name strings in the actual installed
executable, but they may be internal/GUI-only and are absent from the vendor's
installed SDK declarations. Do **not** mistake this positive string evidence
for a callable API, nor absence from particular resources for a universal
negative. The prior #477 overall verdict remains **NO SUPPORTED ROUTE
IDENTIFIED**, not “impossible.” Only separately approved and independently
reviewed API evidence could change the supported-route classification; no
native probe was authorized or attempted here.

Maintain #473's **non-GUI, same-UID native edit** acceptance without changes;
no M4 approval or #312/#313 dispatch, no #480 upgrade and no #474 release.
Additional native effects or design alternatives need separate approvals.

## Verification record

- Linux Zodex worktree `zodex/489-resolve-21-1-1-same-uid-roll-static-bina`,
  baseline `origin/main` at `3e1a7d08`; phase-1 scanner commit `3f2591c9`.
- `uv run --frozen pytest -q tests/test_issue489_static_resolve_audit.py tests/test_issue477_sdk_inventory.py`: **56 passed** after adjusting the fixed hard binary ceiling to fit the observed 1,049,754,864-byte installed executable.
- `uv run --frozen ruff check ...` and `ruff format --check ...`: **passed**;
  `uv run --frozen mypy python tests`: **passed, 367 source files**.
- `VITEST_MAX_WORKERS=1 npm run validate:fast`: **exit 1**, despite generated
  contracts PASS, TypeScript lint PASS and TypeScript types PASS. TS test
  workspaces produced **four 5-second timeouts** in two unchanged files:
  `packages/contracts/test/qualification-output-proposals-v2.test.ts` (three)
  and `packages/public-page-capture/test/authorization-integration.test.ts`
  (one). The branch introduces no TypeScript code changes and the timed-out
  contracts test file SHA matches `origin/main`. Focused retries passed:
  contracts **30/30**, capture **7/7**. This is consistent with existing
  load-dependent test timing sensitivity, not a scanner regression.
  **A separate whole-gate execution on `origin/main` was not performed;
  the fast gate is not claimed green**. No timeouts/assertions were relaxed.
- Reversible mutation tests: setting `mayUnblock473Or312=true`, ignoring the
  impossible-name control, removing file `O_NOFOLLOW` and bypassing private
  resource exclusion each produced expected failing tests (1, 1, 1 and 3
  failures). Source restored after each mutation; final focused **56 passed**,
  Ruff/format/mypy green, `git diff --check` green. Manual full-diff review
  performed, no unrelated code changes.
- Mac Bridge read-only bundle identity, four matching hashes, 1.05 GB
  executable SHA, 430 KB signed ResolveMCP SHA, 69 KB MCP archive SHA,
  selected exact/raw strings, archive tool-name list and public Examples grep
  **verified**. No app/script/API/tool invocation, native write, media or
  user-configuration access.
