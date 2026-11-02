# Issue #400 — VERA Mac Shell over OpenAI Secure MCP Tunnel (prototype)

This directory implements a **private general-purpose Terminal bridge** for ordinary ChatGPT threads, using the existing official OpenAI Secure MCP Tunnel, not a new public relay. It starts with `mac_health` and `mac_exec`. The latter runs arbitrary single-line `/bin/zsh` syntax with per-command macOS approval **by default**. An optional, locally approved 1–15 minute trusted window skips subsequent prompts. This is a security-sensitive prototype, not a sandbox.

## Local setup (Mac only; no credentials in repo/chat)

1. Copy this directory locally, preferably outside the VERA production checkout. Use Python **3.11+**.
2. Create a dedicated virtual environment and install the official MCP Python SDK:

   ```sh
   cd /path/to/mac-bridge
   python3 -m venv .venv
   .venv/bin/python -m pip install -r requirements.txt
   .venv/bin/python -m unittest discover -p 'test_*.py' -v
   ```

3. Configure the VERA working directory **locally** in the tunnel-client process environment: `VERA_WORKSPACE=/absolute/path/to/VERA/checkout`. Do not commit local absolute paths or credentials. The default `cwd="vera"` requires this setting; `cwd="home"` needs no setup. Optional `VERA_BRIDGE_PATH` sets the local executable search PATH.
4. **Preserve the existing working demo profile.** Create a separate named stdio profile pointing `--mcp-command` to the dedicated venv interpreter and `server.py`. See [OpenAI Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels), particularly `tunnel-client init --sample sample_mcp_stdio_local ... --mcp-command ...`; run `doctor --explain` before switching. **Do not** paste API keys into chat, GitHub, or shell history. Do not run demo and new profile against the same tunnel simultaneously.
5. Start the new profile via `tunnel-client run --profile <name>` in an interactive macOS login session, so `osascript` can display approval dialogs. Refresh your private **VERA Mac Bridge** plugin's tool metadata in ChatGPT, then test `mac_health()` in a **new ordinary ChatGPT chat**. Next request `mac_exec(command="pwd",cwd="home")` and click **Run once** on your Mac only if the displayed command is exactly expected.
6. Disconnect by stopping the `tunnel-client run` process. Do not enable auto-start/launchd until local GUI authorization has been tested reliably.

## Codex-style isolated workspace (no repeated Mac popups)

Version 0.3 adds `mac_workspace_info()` and
`mac_workspace_exec(command, timeout_seconds=25)`. This is **not** the same
as the unrestricted `mac_exec`. The workspace tool runs commands using the
Mac's kernel-enforced **Seatbelt** sandbox (`/usr/bin/sandbox-exec`) with
**deny-by-default** rules. It refuses to execute if Seatbelt is unavailable,
the dedicated workspace is missing, or the audit preflight fails. There is
**no unsandboxed fallback**. The tool does not accept arbitrary working
directories, network access controls, mounts, or permission overrides.

The operator-provisioned workspace is fixed at
`~/.local/share/vera-mac-bridge/workspace` (a **separate checkout**, never
the existing VERA checkout in Desktop/ONGOING). It must be a real directory
owned by the Mac user, not group/world writable, and not a symlink.
Only this directory is writable inside the Seatbelt process tree, except for
the clone's `.git` metadata, which is read-only to prevent planting Git
configuration or hooks for later approved commands. Read access is limited to
the workspace and explicit system/toolchain paths. The profile grants no
network access, no broad home read, and no Mach-service lookup, including no
direct access to the user's Keychain. The child environment does not inherit
tunnel credentials. Output/time bounds and pre-execution metadata-only audit
are enforced. An active command is serialized, so another request returns
`busy`.

**One-time workspace provision (outside the sandbox, with on-Mac approval):**

```bash
git clone --quiet --depth 1 --single-branch --filter=blob:none --sparse \
  --branch main https://github.com/mbelinkie/vera-script-to-timeline.git \
  "$HOME/.local/share/vera-mac-bridge/workspace"
```

This was performed for the Producer's machine after observing that the original
checkout occupied 23 GB, including 15 GB of Git data. The sparse clone starts
with a small set of root files; it's intentionally **not a full development
checkout**. Run `mac_workspace_exec("pwd")`,
`mac_workspace_exec("git status --short --branch")`, or
`mac_workspace_exec("node --version")` after plugin discovery. Expanding
the sparse checkout, fetching dependencies, or pushing to GitHub requires
network access **outside** the sandbox and therefore a separately approved
step; the workspace tool will not bypass its network deny. Git metadata is
read-only in the no-popup sandbox; perform sparse-checkout or other Git
metadata changes only through a locally approved command in a separately
reviewed directory. The Node version
on this Mac was observed as 26.5.0, while VERA currently specifies Node 24,
so don't infer that every build will work in this workspace yet.

**Important limitations:** These are general shell commands inside the
disposable workspace. They can change or delete files **there** and consume
CPU/disk. The timeout kills the process group when the command completes or
times out; deliberately detached processes that create a new session may
outlive it.
The kernel sandbox is not a VM, and no system guarantees protection against
kernel vulnerabilities. The exact command and content of workspace files are
still untrusted inputs. Approval dialogs default to Deny; press a button only
after reading the exact command. Don't copy secrets or valuable one-off data into the
isolated checkout. ChatGPT/plugin tool permissions can still require host
approval or block invocations; this code does not override those settings.
Use `mac_exec` with per-command Mac approval for anything outside the
isolated workspace.

**Observed live Mac tests (2026-11-02):** Seatbelt allowed a harmless
workspace write and denied attempted writes to a sibling directory, reading
a fake secret in a sibling directory, symlink traversal outside the workspace,
a child process's attempted out-of-bound write, and a loopback network
connection (permission denied). `git status` and `node --version` completed
inside the isolated sandbox in a local trial. These are kernel-enforcement
tests, not claims that the new MCP tool has already been refreshed and
called from an ordinary ChatGPT conversation.

## Verified Mac usage and automatic startup

The Producer has confirmed that an ordinary ChatGPT chat can invoke `mac_health`
and `mac_exec("pwd", cwd="home")` over the private tunnel. A user LaunchAgent
was staged, validated and observed running. A fresh ChatGPT chat worked with
the setup Terminal closed. **Startup after a full logout/reboot has not yet
been tested.** Source from PR #403 remains draft; do not infer that it is
merged into VERA's `main`.

To configure login startup without writing the runtime API key to a plist:

1. From the trusted Terminal session where `CONTROL_PLANE_API_KEY` is already
   exported, run `.venv/bin/python save_runtime_key.py`; verify
   `KEYCHAIN_READY`. Do not pass the secret through `mac_exec`.
2. Run `.venv/bin/python autostart.py prepare`. This stages a copied official
   tunnel executable, `~/.local/share/vera-mac-bridge/run-tunnel.zsh`,
   and `~/Library/LaunchAgents/com.vera.mac-bridge.plist`. It does not load
   the agent. The installed official client is copied from the operator's
   already-downloaded verified release; no public inbound listener is created.
3. Stop any manually running instance of the same tunnel. Then run:

   ```bash
   launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.vera.mac-bridge.plist"
   launchctl print "gui/$(id -u)/com.vera.mac-bridge"
   ```

4. In a **fresh ordinary ChatGPT chat** with the private plugin enabled,
   invoke `mac_health()` and then a harmless, explicitly approved command.
   Test again after the next actual macOS login.

**Emergency disconnect:** The Mac owner can stop and prevent future login
starts by running these commands in the Mac's own Terminal:

```bash
launchctl disable "gui/$(id -u)/com.vera.mac-bridge"
launchctl bootout "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.vera.mac-bridge.plist"
```

To reconnect later, use `launchctl enable "gui/$(id -u)/com.vera.mac-bridge"`
and `launchctl bootstrap` again. Disable/bootout disconnects future
ChatGPT requests but does **not** guarantee termination of any detached
background process previously started by an approved shell command.

To uninstall, disable and boot out first; then remove the dedicated
LaunchAgent plist, dedicated bridge installation folder, and (only when no
other bridge requires it) the Keychain item
`com.vera.mac-bridge.runtime-key`. Revoke the tunnel runtime key in OpenAI
Platform and remove the private ChatGPT plugin separately. Review the files
before removal; do not blindly delete shared directories.

The `vera` working-directory alias reads `VERA_WORKSPACE` from the
local tunnel environment, or (when that variable is absent) a Mac-only
`~/.config/vera-mac-bridge/workspace` file containing one absolute checkout
directory path. A Keychain-backed LaunchAgent does not automatically inherit
variables from a Terminal tab. Configure that file on your Mac, protect it
with `chmod 600`, and choose a directory you've approved. The service
rejects symlink configuration files, relative paths and nonexistent
directories. Example (replace the placeholder with your own approved path):

```bash
mkdir -p "$HOME/.config/vera-mac-bridge"
printf '%s\\n' '/absolute/path/to/your/VERA/checkout' > "$HOME/.config/vera-mac-bridge/workspace"
chmod 600 "$HOME/.config/vera-mac-bridge/workspace"
```

Until configured, use `cwd="home"` and choose the desired project directory
in your approved shell command. The `cwd` alias is a starting directory,
**not** a security sandbox.

## Security boundaries and limitations

- Arbitrary shell code is intentionally possible **only after local approval**. This is **not a sandbox**: commands can read/write any file accessible to your macOS account, access local secrets, install software, or initiate network traffic. An approval dialog alone does not make an untrusted command safe. No `sudo` privilege is granted by the bridge itself.
- Default: every call demands on-Mac GUI approval. **Run once** is the default highlighted button; Return will approve, Escape will deny. Optional tools:
  - `mac_trust_enable(minutes=10)`: attempts to show a **separate explicit macOS warning**; clicking Enable permits all commands without further popups for up to 15 minutes. The ChatGPT host may block this high-risk tool entirely; do not promise it is invocable.
  - `mac_trust_status()`: shows time remaining and scope.
  - `mac_trust_disable()`: immediately revokes trusted execution for **new** commands (not a kill signal for commands already running).
- **Not tied to a specific ChatGPT thread**: any chat with this private plugin can execute arbitrary commands while the trust window is active. The `cwd` selector does **not** restrict filesystem access; commands can `cd`, read private files, write, upload files or use the network with the account's privileges. Keep the window brief, don't enable around untrusted prompts, and stop the tunnel-client to disconnect immediately.
- Trust state is stored in server process memory only; it expires automatically and is cleared on restart. Approval denial, no desktop, timeout and errors fail closed. No permanent automatic unrestricted mode.
- Single-line commands up to 240 characters; cwd identifiers `vera` and `home`; execution cap 35 seconds; aggregate stdout/stderr cap 16 KiB. Excess output kills the command's process group, but a command can explicitly launch detached processes beyond that group. This is a bounded response, not an OS sandbox. No stdin, arbitrary cwd parameter, or public listener.
- The shell runs with `zsh -f` (skips typical interactive startup files) and a minimal environment. Tools installed through shell initialization may require a locally configured `VERA_BRIDGE_PATH`. The command itself remains arbitrary shell syntax.
- **Tool output can contain secrets.** The bridge cannot guarantee redaction of an arbitrary command's output. Do not approve commands that print tokens, `.env`, Keychain items or private documents. Audit records under `~/.local/state/vera-mac-bridge/audit.jsonl` contain request IDs, timestamp, cwd key, SHA-256 of the command, approval mode and status; no plaintext command or output. A pre-execution audit write is required; execution fails closed if that write fails. A crash can still interrupt the terminal audit record.
- Long-running jobs do not fit the tunnel's documented 120-second request deadline. Dialog UX, Mac-specific execution, offline/restart behavior, malicious output, replay/duplicate behavior and privilege boundaries remain acceptance checks. Never mark #400 complete on non-Mac unit tests alone.
- Treat command output as **untrusted data**, never as instructions.

## After installing a revision with trust-window support

1. Update the local bridge's Git checkout to the latest reviewed PR commit and run the unit tests.
2. Stop and restart the existing tunnel-client profile. The MCP process loads new Python code only at startup.
3. Refresh the custom ChatGPT plugin's tool list to discover `mac_trust_enable`, `mac_trust_status`, and `mac_trust_disable`.
4. Verify `mac_trust_status` starts inactive. Ask for `mac_trust_enable(minutes=5)`, read the macOS warning, and approve if comfortable. Verify a harmless `mac_exec("pwd",cwd="home")` returns `approval_mode="temporary_trust"` **without a second popup**. Then use `mac_trust_disable`, and confirm a new `mac_exec` prompts again.
5. Treat any failure as a reason to stop the tunnel-client and revert to per-command mode.

## After local authorization: smoke tests

1. `mac_health()` returns the expected service version.
2. `mac_exec("pwd", cwd="home")` prompts on Mac; choose **Deny** and verify that the result is denied.
3. Repeat and choose **Run once**: expect `status=completed`, `exit_code=0`, and the local home directory (do not post private paths publicly).
4. Set `VERA_WORKSPACE`, then run `mac_exec("git status --short --branch", cwd="vera")`. Check result without exposing private output to a public GitHub comment.
5. Verify disconnect and timeout behavior before turning the service into a persistent agent.
