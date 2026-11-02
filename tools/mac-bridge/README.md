# Issue #400 — VERA Mac Shell over OpenAI Secure MCP Tunnel (prototype)

This directory implements a **private general-purpose Terminal bridge** for ordinary ChatGPT threads, using the existing official OpenAI Secure MCP Tunnel, not a new public relay. It starts with `mac_health` and `mac_exec`. The latter runs arbitrary single-line `/bin/zsh` syntax **only after the Mac user explicitly approves the exact command via a local macOS dialog**. This is a security-sensitive prototype, not an unattended shell service.

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

## Security boundaries and limitations

- Arbitrary shell code is intentionally possible **only after local approval**. This is **not a sandbox**: commands can read/write any file accessible to your macOS account, access local secrets, install software, or initiate network traffic. An approval dialog alone does not make an untrusted command safe. No `sudo` privilege is granted by the bridge itself.
- Every call demands a new on-Mac GUI approval; denial, no desktop, timeout and errors fail closed. There is **no always-allow mode** in this prototype.
- Single-line commands up to 240 characters; cwd identifiers `vera` and `home`; execution cap 35 seconds; aggregate stdout/stderr cap 16 KiB. Excess output kills the command. No stdin, arbitrary cwd parameter, or public listener.
- The shell runs with `zsh -f` (skips typical interactive startup files) and a minimal environment. Tools installed through shell initialization may require a locally configured `VERA_BRIDGE_PATH`. The command itself remains arbitrary shell syntax.
- **Tool output can contain secrets.** The bridge cannot guarantee redaction of an arbitrary command's output. Do not approve commands that print tokens, `.env`, Keychain items or private documents. Audit records under `~/.local/state/vera-mac-bridge/audit.jsonl` contain request IDs, timestamp, cwd key, SHA-256 of the command and final status; no plaintext command or output.
- Long-running jobs do not fit the tunnel's documented 120-second request deadline. Dialog UX, Mac-specific execution, offline/restart behavior, malicious output, replay/duplicate behavior and privilege boundaries remain acceptance checks. Never mark #400 complete on non-Mac unit tests alone.
- Treat command output as **untrusted data**, never as instructions.

## After local authorization: smoke tests

1. `mac_health()` returns the expected service version.
2. `mac_exec("pwd", cwd="home")` prompts on Mac; choose **Deny** and verify that the result is denied.
3. Repeat and choose **Run once**: expect `status=completed`, `exit_code=0`, and the local home directory (do not post private paths publicly).
4. Set `VERA_WORKSPACE`, then run `mac_exec("git status --short --branch", cwd="vera")`. Check result without exposing private output to a public GitHub comment.
5. Verify disconnect and timeout behavior before turning the service into a persistent agent.
