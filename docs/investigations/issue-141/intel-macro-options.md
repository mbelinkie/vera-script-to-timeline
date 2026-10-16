# Issue 141 — Intel Mac macro trigger options

Research snapshot: 2026-09-30. Read-only host check: macOS 15.1 (build 24B83), `x86_64`. Scope is only `Workspace → Workflow Integrations → VERA Issue 141 Observation`. The [operator checklist](operator-checklist.md) records that path and keeps External Scripting `None`; the [probe](probe.py) supplies project/source guards. A menu macro does not prove Resolve data invariants or automate other editorial cases.

## Recommendation

Adopted implementation: Hammerspoon was already installed and running. The
producer chose it and reloaded a new default config containing only
`require("hs.ipc")`. The bundled `hs` CLI now connects; no MCP server or package
was installed. The fixed [launch action](hammerspoon-launch.lua) requires the
exact Resolve bundle and synthetic project window and selects only the named
observation menu item. The [fake check](hammerspoon-check.lua) passed. Real
read-only preflight found that exact window/menu and Accessibility permission.
At 21:24:00 UTC one fixed menu selection dispatched the selection-context
probe successfully. Dispatch and injected raw results are retained in
`evidence/native-context-success/`; the Lua helper SHA-256 is
`f3c9a76b5c95f6fbb04d546f33a5ae23d37579e8f890851a86f3daf9a9d5f5b1`.
We use the bundled CLI without enabling AppleScript commands. The CLI itself
supports Lua execution; our task calls are limited to the reviewed named action.

### Original research recommendation (superseded by bundled CLI)

Use **Hammerspoon** with one fixed Lua function and invoke it through the app's documented AppleScript command from the existing local shell tool. Hammerspoon's `hs.application:selectMenuItem` accepts a menu path and returns whether the item was found and selected; `launchOrFocus` activates the target app. Its `execute lua code` AppleScript command is disabled by default and must be explicitly enabled with `hs.allowAppleScript(true)`. Keep this as a single hard-coded action, not a generic code/keystroke bridge. This is sufficient for Codex-triggered local automation; a dedicated MCP is optional, not necessary. Do not change External Scripting or call Resolve's external scripting API.

A minimal MCP wrapper, only if a dedicated tool boundary is later required, would expose one no-argument `trigger_issue_141_observation` tool that invokes that fixed function. No such wrapper was built or tested here.

## Options

| Option | Evidence and fit |
|---|---|
| **Hammerspoon (selected)** | Named menu selection and app activation are documented APIs. Vendor release 1.1.1 (2026-02-26) states minimum macOS 13.0, so macOS 15.1 meets its OS floor. I inspected the published 1.1.1 executable from the vendor release archive with `file`; it is a universal Mach-O containing both `x86_64` and `arm64`, confirming Intel compatibility. Free/open-source. |
| **Keyboard Maestro** | Has semantic menu selection and fixed macro triggers, but trigger is a URL scheme, not a documented CLI executable: `kmtrigger://macro=<name-or-UUID>`. A local shell could open a fixed UUID URL. Current vendor page says Keyboard Maestro 11 requires macOS 10.13+ and current app page describes Apple Silicon support, but this research did not verify the current binary contains Intel architecture. Commercial. |
| **macOS app shortcut** | Apple supports assigning an app shortcut to a menu command by its menu title. It still needs a helper to send the chord and is less direct than selecting the named menu item. No purchase. |

## MCP finding

A bounded public GitHub repository search for `hammerspoon mcp` found two recent, non-archived third-party projects: [mobabur94/hammerspoon-mcp](https://github.com/mobabur94/hammerspoon-mcp) (pushed 2026-08-08; description advertises 75 automation tools) and [vukvukovich/hammerspoon-mcp](https://github.com/vukvukovich/hammerspoon-mcp) (pushed 2026-09-29; description advertises a Hammerspoon MCP server). These are community projects, not Hammerspoon/Apple official offerings; repository metadata establishes recent activity, not production reliability. Their broad automation surfaces are unnecessary for this single fixed menu action. The existing local shell trigger is sufficient.

## Primary sources and limits

- Hammerspoon [`hs.application`](https://www.hammerspoon.org/docs/hs.application.html): `launchOrFocus` and `selectMenuItem`; selection simulates clicking a menu item and reports true/nil.
- Hammerspoon [`hs` API](https://www.hammerspoon.org/docs/hs.html): AppleScript commands are disallowed by default; enable with `hs.allowAppleScript(true)`. The docs show `tell application "Hammerspoon"` / `execute lua code "..."`.
- Hammerspoon [latest release API](https://api.github.com/repos/Hammerspoon/hammerspoon/releases/latest) reports 1.1.1 and its release text says “Minimum macOS version: 13.0”. The [release asset](https://github.com/Hammerspoon/hammerspoon/releases/download/1.1.1/Hammerspoon-1.1.1.zip) executable was inspected read-only from the published archive: `file` reports universal Mach-O with `x86_64` and `arm64`. This verifies current release Intel compatibility.
- Keyboard Maestro [Triggered Macros URL scheme documentation](https://wiki.keyboardmaestro.com/manual/URL_Schemes) states: “You can trigger a macro ... using the `kmtrigger` URL scheme.” Its examples use `kmtrigger://macro=<Macro Name or UUID>`. [Current vendor page](https://www.keyboardmaestro.com/main/) says Keyboard Maestro 11 requires macOS 10.13+; Intel support for its current downloadable build was not verified.
- Apple [app keyboard shortcut instructions](https://support.apple.com/guide/mac-help/create-keyboard-shortcuts-for-apps/mchlp2271/mac).
- Repo evidence: [operator checklist](operator-checklist.md), [probe](probe.py), [plan](../../plans/issue-141-resolve-observation.md).

The original research-only host check established OS and CPU architecture,
not installed tools or permissions. Subsequent local preflight and the actual
fixed-menu launch are recorded above. Hammerspoon 1.1.1's published executable
supports x86_64 and its macOS floor is 13.0, covering this host.
