# #479 — Resolve Studio 21.2 on the existing Intel Mac: read-only coexistence gate

**Disposition (2026-11-08): NO-GO for installing or independently testing 21.2
on this Mac.** Keep the working Studio **21.1.1 build 10** installation
untouched. **The direct Blackmagic 21.2 installer CPU slices and package
requirements are UNKNOWN**, not proved arm64-only; this is a **support and
coexistence NO-GO**, not a claim that an Intel 21.2 executable cannot exist.
**Conductor must NOT promote/launch #480** on the strength of this report or
#479 closure. #480 requires independently proved, vendor-supported same-machine
coexistence GO **and** fully accepted #473, plus its own installation approval.
No installation, Resolve launch, SDK import, project access, owner-lock
acquisition, native test, or shared-host configuration change occurred.

This assessment is distinct from #477's negative *same-UID roll* finding and
does not change #473's native acceptance. The issue explicitly authorizes
read-only #479 work in parallel with incomplete #473.

## Evidence ledger — do not mix support requirements with binary contents

| ID / class | Source or command | Observation | What it **does not** prove |
| --- | --- | --- | --- |
| H1 / host read-only, 2026-11-08 | Mac Bridge `uname -m`, `sw_vers -productVersion`, `sw_vers -buildVersion`, `sysctl -n machdep.cpu.brand_string` | `x86_64`, **macOS 15.1 (24B83)**, **Intel Core i9-9880H @ 2.30 GHz** | No 21.2 compatibility verdict alone |
| H2 / host read-only | `system_profiler SPDisplaysDataType` (GPU fields only), `sysctl -n hw.memsize` | **Intel UHD Graphics 630**, dynamic VRAM up to **1536 MB**, **AMD Radeon Pro 5500M 4 GB**; both report **Metal 3**; **16 GiB RAM** | GPU support cannot override a stated Apple-silicon CPU floor |
| H3 / host read-only | `df -h /Applications` | **35 GiB available**, ~97% used on a 932 GiB data volume (snapshot of Nov 8) | Not evidence of enough space for parallel installs, libraries, caches or rollback; future disk use unknown |
| H4 / host read-only | `/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Info.plist`, `plutil` | `CFBundleIdentifier=com.blackmagic-design.DaVinciResolve`; `CFBundleShortVersionString=21.1.1`; `CFBundleVersion=21.1.10010`; `LSMinimumSystemVersion=15.0`; executable `Resolve` | Bundle metadata is not a live Studio-license/version handshake |
| H5 / host read-only | `shasum -a 256` of H4 Info.plist | SHA-256 `7539507115e554d8b936253934c394d9ded2b8f509eb5edd1cb58b047391a2f4` | A metadata hash is not a complete binary/notarization attestation |
| H6 / host read-only | `file` on installed `Contents/MacOS/Resolve` and `codesign -dv --verbose=2` on installed app | **Universal Mach-O with `x86_64` and `arm64` slices**. Developer ID Application: **Blackmagic Design Inc (9ZGFBWLSYP)**; Team ID `9ZGFBWLSYP`; identifier as H4 | This is the **installed 21.1.1 app only**, **not** 21.2 installer architecture; having an Intel slice does not equal official vendor support |
| H7 / host read-only | `pkgutil --pkgs` filtered by Blackmagic, DaVinci and Fusion | Receipts: `DaVinciPanels`, `FairlightPanels`, `ManifestPanels`, `ManifestBlackmagicRawPlayer`, `BlackmagicRaw_resolve`, `ManifestLite`, `DaVinciKeyboards`, `Manifest` (all `com.blackmagic-design.*`) | Absence of a simple `DaVinciResolve` receipt in this filter is **not** proof that an installer or upgrade is app-only or isolation-safe; exact 21.2 BOM/receipt actions unknown |
| H8 / host read-only | `ls -ld` on known system paths; limited OFX first-level names only | `/Applications/DaVinci Resolve`, system `.../Developer/Scripting`, `/Library/OFX/Plugins` exist; OFX names: `3D LUT Creator Plugin.ofx.bundle`, `ArtlistPlugins.ofx.bundle` | Did not inspect plug-in internals or assess 21.2 ABI compatibility |
| H9 / host read-only | Exact *existence only* checks of known user/system paths | `$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve` and `$HOME/Movies/CacheClip` exist; `$HOME/Library/Caches/Blackmagic Design` and `/Library/.../Support/Resolve Disk Database` were not present at those exact checked paths | No project-library enumeration, schema, database, media or cache data was accessed; other locations may exist |
| H10 / host read-only | `find` only fixed `$HOME/Library/LaunchAgents` level and names containing `vera`; no plist contents | VERA conductor, Mac bridge, native queue/campaign worker/monitor, self-hosted runner launch-agent names exist | A file's presence does not prove it is loaded/running; effects, secrets and configuration not inspected |
| H11 / host read-only | System `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/` | Installed SDK stub SHA-256 `2755259ef5f57b5d477786f799892e5b86ed3945db84bf88fb69bf751b36e651` (matches [#477](issue-477-native-roll-feasibility.md)); module wrapper SHA-256 `41514aac7c9ae7a8c70db7b2516593cbbbb97890f4cfbb6810ccceb13bea2748` | These files were installed with the old release. No official 21.2 SDK bytes examined |
| B1 / official vendor landing page | [Blackmagic direct support / release note for Studio 21.2](https://www.blackmagicdesign.com/support/readme/630fd2cb208a46df9493de661a76628a) and [Blackmagic support center](https://www.blackmagicdesign.com/support/) | Official 21.2 release-note entry identifiable. Its dynamic readme/download presentation did **not** expose authenticated installer binary slices, per-architecture BOM, SHA-256, signature or an explicit independent-install guarantee in this examination | **Cannot** establish direct-vendor 21.2 installer Intel compatibility or Apple-silicon-only binary composition |
| B2 / vendor's *different distribution* | [Blackmagic Design Inc Studio listing at Apple App Store](https://apps.apple.com/us/app/davinci-resolve-studio/id900392332?mt=12) | Says **Apple silicon** and **macOS 15+**; the listing explicitly distinguishes the App Store build from the full/direct Blackmagic distribution | **Not** authenticated proof of requirements or slices of the **direct** 21.2 Studio installer |
| P1 / published secondary release-note reproduction | [ProVideo Coalition, Sep 8 2026, Resolve 21.1 release](https://www.provideocoalition.com/davinci-resolve-21-1-is-a-huge-update/) and [MotionMedia, Studio 21.1.1 release](https://www.motionmedia.com/mm-blog/davinci-resolve-studio-21-1-1-update/) | Their published 21.1/21.1.1 macOS requirements say **Apple silicon** and **macOS 15+** | This is **not** evidence that every 21.1.1 shipped executable lacked Intel: H6 directly disproves that inference |
| P2 / earlier published requirement | [20.3.2 requirements reproduction](https://www.samdb.co.za/blogs/blog/2026/02/12/davinci-resolve-studio-20-3-2-from-blackmagic-design/); [21 release reproduction](https://tweakers.net/downloads/77204/davinci-resolve-21.html) | **20.3.2** allowed Apple silicon **or a Metal GPU**; **21.0** was published with Apple-silicon minimum | Published support floor changed by the 21 major release; the date of cessation of Intel **binary shipping** cannot be inferred |
| P3 / independent 21.2 reporting | [CineD, 21.2 release, November 2026](https://www.cined.com/davinci-resolve-21-2-released-proled-xdr-touch-support-gen-6-color-science-luts-up-to-5x-faster-rendering-on-m5-pro-and-m5-max/) | Reports 21.2 retained 21.1 minimum: **Apple silicon, macOS 15+**; warns that newer-saved projects may not open in 20.3.2 | Secondary, not a direct-install PKG or vendor-certified independent coexistence guide |
| B3 / official announcement | [Blackmagic Design Sep 8 2026 announcement](https://www.blackmagicdesign.com/media/partial/release/20260908-03) | Announces 21.1 features; no announcement of Intel support removal was identified here | Silence in a press release is not evidence of continued support |

**Important reconciliation:** The installed **21.1.1.10** app *really has*
`x86_64` and `arm64` slices despite 21.1's published Apple-silicon minimum.
It is reasonable to say this 21.1.1 installation works on this Intel host,
consistent with previously recorded native runs (RK-02), **but not** that
Intel is officially supported for 21.1 or that the uninspected 21.2 direct
installer is incapable of running. Requirements, a signed executable's actual
architecture, and supported *independent coexistence* are three distinct gates.

**Unacquired 21.2 identity:** There is no downloaded/verified direct Studio
21.2 Mac PKG/DMG in this assessment; therefore its SHA-256, code signing,
notarization, executable slices, installer distribution scripts, receipts,
version-specific SDK, minimum OS/CPU checks and any architecture-specific
components are **NOT VERIFIED**. No download or execution was attempted.

## Shared-state and two-version independence assessment

| Resource | What the code/host establishes | 21.2 independent coexistence status |
| --- | --- | --- |
| App path and identity | Current installed app at `/Applications/DaVinci Resolve/DaVinci Resolve.app`, bundle ID `com.blackmagic-design.DaVinciResolve`; existing app universally compiled | **NOT PROVEN.** Two renamed `.app` copies are not supported independent installs; LaunchServices, associated file routes, update/PKG scripts may still target one identity |
| System SDK | `python/vera_timeline_agent/resolve_native_owner.py` sets `_RESOLVE_SCRIPTING_MODULE` to the **global** `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules/DaVinciResolveScript.py` | **NOT ISOLATED.** Neither importing the global module nor selecting an app path proves the module and runtime are paired to the intended version |
| Native extension/bootstrap | Installed wrapper first imports `fusionscript`, then tries `RESOLVE_SCRIPT_LIB`, then the hard-coded `/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so`; replaces `sys.modules[__name__]` with the native extension | **NOT ISOLATED.** `RESOLVE_SCRIPT_LIB` is one component, not a complete supported multi-version routing protocol; wrappers/default paths, `ResolvePython` and inherited imports remain version-sensitive |
| External vs injected API | RK-02 distinguishes Studio 21.1.1 injected Python **3.14.7 / External Scripting None** and `Local` parent/external API. Parent `_local_resolve_connection()` imports shared global wrapper and calls `scriptapp("Resolve")` | **NOT PROVEN.** A version-specific interpreter, module, scripting server endpoint, injected bundle and direct host identity must all match; process/port selection cannot be guessed |
| Packages, frameworks and receipts | H7 lists shared Blackmagic receipt namespace; H8 identifies global SDK and OFX paths; H6 signature/bundle identity | **NOT PROVEN.** 21.2 Mac installer BOM/scripts, receipt replacements, shared frameworks and plug-in installation effects not obtained; a successful second `.app` extraction would not answer these |
| Preferences, caches, plug-ins, handlers | H9 shows user-level vendor support and media cache paths; global OFX plug-ins exist; LaunchServices and file associations are shared at OS level | **NOT ISOLATED.** Different `.app` names do not partition preferences, cache, plug-in support, saved defaults, `.drp`/`.dra` handlers or activation state |
| Project libraries/database | No database or media reads occurred. Documentation warns newer projects opened in 21.1/21.2 can stop opening in 20.3.2; 21.1.1↔21.2 direct reverse compatibility **unverified** | **NOT PROVEN.** Need distinct library/DB credentials and a vendor-supported schema policy; merely pointing two executables to the same DB risks irreversible upgrades |
| Activation | Current installed Studio has documented previous native proof, not a new live entitlement check; dongle/cloud/license keys were **not read** | **NOT PROVEN.** License reactivation/seat consumption or two-instance behavior requires official guidance; do not interrogate activation secrets |
| VERA native ownership and durability | `resolve_native_owner.py` uses one `~/.local/state/vera/resolve-delivery/native-owner.lock`, parent-active marker, output attempts/targets and `VERA_NATIVE_OWNER_FD`; H10 shows workers/launch agents exist on Mac. Repository worker pins include Node 24.19.0 (`qualification_output_package_v2.py`), FFmpeg/FFprobe 8.1.2 (`qualification_output_decode_v2.py`), and earlier RK-02 injected Python 3.14.7 | **NOT ISOLATED.** No second active worker, conflicting owner, new op IDs or historical receipt reuse allowed. Isolating app files alone will not isolate VERA's target/operation state |
| Disk and rollback | H3 reports **35 GiB** free, existing 21.1.1 unmodified | **NOT PROVEN.** No verified second-install footprint, isolated project copy, backup/recovery or reinstall-free rollback evidence exists. Do not risk the baseline to measure space |

The installed `DaVinciResolveScript.py` wrapper was **read as text only** on
the Mac (no Python import). Its SHA-256 and exact paths are in H11. The
on-disk `ResolvePython` directory and Fusion libraries exist under the
current app. No claim is made about running services, target/project state,
worker readback or a 21.2 API connection. Existing [#477](issue-477-native-roll-feasibility.md)
also establishes that published 21.2 setters do **not** prove the demanded
non-GUI same-UID roll.

## Isolation alternatives and the required (not authorized) future gate

1. **Recommended now: leave the original Intel Mac unchanged.** The
   Apple-silicon-only published 21.1/21.1.1 requirements and secondary 21.2
   reporting are adverse to this CPU. The **direct** Studio 21.2 installer
   support status, binary slices and
   coexistence are additionally unproved. No action may be taken on this
   evidence alone.
2. A **separate vendor-supported Apple-silicon Mac with its own OS/user state,
   library, cache, SDK, launch services, activation handling and VERA owner/log
   namespace** is the cleanest candidate. It requires a separately scoped
   approval, official install evidence and a fresh #480 design; it does not
   retroactively make this Intel host a GO.
3. A separately booted **APFS volume or standalone OS** *might* isolate OS
   receipts and `/Library`/user state better than two app folders, but no
   Blackmagic guarantee for two boot environments has been proved, and this
   machine's CPU would still be Intel. No volume creation, boot changes or
   installer trial is authorized.
4. A plain renamed/copied `.app`, `RESOLVE_SCRIPT_LIB` override alone, Rosetta
   (for the **opposite** architecture direction), or two VERA processes on the
   same native owner are **not acceptable substitutes**. They cannot certify
   independent official versions, SDK routing or a non-upgraded shared DB.

**Hypothetical future GO checklist; none is satisfied by this ticket:**

- Obtain *direct-from-Blackmagic* version-specific written CPU/OS/Studio
  requirements that **explicitly support the intended hardware**, plus
  authenticated installer hash, notarization/codesign, CPU slices, distribution
  scripts, complete BOM/receipts and SDK identity **without executing** it.
- Obtain official documentation/support confirmation that the **two versions
  are allowed to be independently installed and selected on one Mac**, with
  version-pinned wrapper/SDK/`fusionscript`/ResolvePython, app routing,
  persistent caches, plug-ins, file handlers and licensing kept independent.
- Produce an independently isolated library/DB (no cross-version open or
  migration), media fixture/cache, owner lock, operation journal, worker and
  immutable version selection; prove safe old-version recovery and rollback
  **without reinstalling**. No project tests before separate approval.
- Require **#473 fully accepted** and a *new explicit authorized #480 install*
  gate, including safe resources, success/readback and a no-impact fallback.
  #479 itself only authorizes offline checks, not vendor downloads, installation
  or runtime testing.

**Conductor rule:** A `NO-GO` or `UNKNOWN` #479, even if merged/closed,
**must leave #480 blocked** and must not trigger installation, testing,
native SDK access, #312/#313, extra campaigns or baseline changes. #484
can still proceed as documentation-only public API research.

## Reproduction (read-only, no native app or SDK execution)

The exact Mac Bridge inspections above used only `uname`, `sw_vers`, `sysctl`,
`df`, `system_profiler` with GPU-only selection, `plutil`, `file`, `codesign -dv`,
`pkgutil --pkgs`, `ls`, `test -e`, narrowly bounded `find`, `sed` on the known
SDK wrapper and `shasum -a 256` on vendor text/plist. No project-library
contents, project names, media contents, license secrets or user preferences
were read. We did **not** inspect any actual 21.2 vendor installer, and do not
claim that this environment can verify its internals.

The optional Python helper is intentionally **static-only**:

```sh
# On a Mac where the existing app is already present, print only static
# Info.plist SHA/version and Mach-O CPU declarations. NO Resolve start/import.
uv run --frozen python -m vera_timeline_agent.issue479_macho_inventory \
  --app '/Applications/DaVinci Resolve/DaVinci Resolve.app'

# In the isolated VERA worktree; fake bundles only, no real Resolve dependency.
uv run --frozen pytest -q tests/test_issue479_macho_inventory.py
uv run --frozen ruff check python/vera_timeline_agent/issue479_macho_inventory.py tests/test_issue479_macho_inventory.py
uv run --frozen mypy python/vera_timeline_agent/issue479_macho_inventory.py
```

`issue479_macho_inventory.py` reads a bounded Info.plist and fixed Mach-O
headers (fat32, fat64, thin), refuses symlinked/non-regular inputs and malformed
architecture bounds, and *always* emits `liveRuntimeVerified=false`,
`vendorSupportVerified=false`, `independentCoexistenceProven=false`,
`mayInstall=false`, `mayLaunch=false`, `mayPromote480=false`. It is not an
installer parser, cannot attest 21.2 itself and makes no GO decision. Tests
use only fake Mach-O/plist data, not Blackmagic binaries. Running this helper
on the Mac was **not** part of this ticket's host inspection; H6 was confirmed
separately by the read-only `file` and `codesign` commands.

**Proven:** host Intel identity, OS/GPU/RAM/free-space metadata, static signed
21.1.1 bundle and universal `x86_64` slice, shared SDK paths, prior static SDK
hashes. **Published but not directly package-verified:** 21.2 Apple-silicon
minimum. **Unverified:** direct 21.2 installer binary, exact PKG side effects,
supported parallel operation, database isolation, activation and rollback.
