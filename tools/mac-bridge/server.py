"""Private MCP server for VERA Mac Bridge.

Launched by OpenAI tunnel-client via stdio.
"""

from mcp.server import MCPServer
from sandbox_core import workspace_exec, workspace_info
from shell_core import mac_exec_local, trust_disable, trust_enable, trust_status

mcp = MCPServer("VERA Mac Shell")


@mcp.tool()
def mac_health() -> dict:
    """Return bridge liveness without executing Terminal commands."""
    return {
        "status": "ok",
        "service": "vera-mac-shell",
        "version": "0.3.0",
        "approval": "per-command-or-local-trust-window",
    }


@mcp.tool()
def mac_exec(command: str, cwd: str = "vera", timeout_seconds: int = 25) -> dict:
    """Request a Terminal command.

    Normally requires on-Mac approval; a locally approved, short trusted
    window may bypass individual prompts.

    command: A single line of shell syntax (max 240 characters) shown verbatim on Mac.
    cwd: 'vera' (locally configured repo) or 'home'.
    timeout_seconds: Execution cap between 1 and 35 seconds.

    Every invocation can read/write local files or use the network *if locally
    approved or when a local trust window is active*. Never use to expose secrets.
    """
    return mac_exec_local(command, cwd, timeout_seconds)


@mcp.tool()
def mac_trust_enable(minutes: int = 10) -> dict:
    """Ask the Mac user to permit ANY command from ANY connected chat for 1-15 minutes.

    This is a temporary machine-wide permission, NOT isolated to one chat,
    NOT a filesystem sandbox and NOT limited to read-only commands.
    The Mac displays a warning dialog and defaults to Deny.
    """
    return trust_enable(minutes)


@mcp.tool()
def mac_trust_status() -> dict:
    """Check whether temporary no-prompt execution is active and when it expires."""
    return trust_status()


@mcp.tool()
def mac_trust_disable() -> dict:
    """Immediately revoke the temporary trust window for new commands."""
    return trust_disable()


@mcp.tool()
def mac_workspace_info() -> dict:
    """Check whether the dedicated, deny-by-default Mac Seatbelt workspace is ready.

    The workspace is isolated from the Producer's real VERA checkout and from
    bridge credentials. This call never launches a shell or changes any file.
    """
    return workspace_info()


@mcp.tool()
def mac_workspace_exec(command: str, timeout_seconds: int = 25) -> dict:
    """Run a shell command only inside the isolated, OS-enforced Mac workspace.

    No Mac approval popup is needed INSIDE this sandbox, because Seatbelt
    denies network and all filesystem reads/writes outside the dedicated
    workspace and the minimal system paths needed to launch basic programs.
    This is NOT access to the Producer's main VERA checkout. Commands may
    change or delete files within the isolated workspace, which can affect
    later workspace tasks. No host safety check is bypassed. If Seatbelt is
    absent or the workspace is not provisioned, the tool refuses to run.
    For unrestricted Mac commands, use mac_exec with per-command approval.
    """
    return workspace_exec(command, timeout_seconds)


if __name__ == "__main__":
    mcp.run()
