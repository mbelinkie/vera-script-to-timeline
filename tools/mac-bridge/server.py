"""Private MCP server for VERA Mac Bridge; launched by OpenAI tunnel-client via stdio."""

from mcp.server import MCPServer
from shell_core import mac_exec_local, trust_disable, trust_enable, trust_status

mcp = MCPServer("VERA Mac Shell")


@mcp.tool()
def mac_health() -> dict:
    """Return bridge liveness without executing Terminal commands."""
    return {
        "status": "ok",
        "service": "vera-mac-shell",
        "version": "0.2.0",
        "approval": "per-command-or-local-trust-window",
    }


@mcp.tool()
def mac_exec(command: str, cwd: str = "vera", timeout_seconds: int = 25) -> dict:
    """Request a Terminal command. Normally requires on-Mac approval; a locally approved, short trusted window may bypass individual prompts.

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


if __name__ == "__main__":
    mcp.run()
