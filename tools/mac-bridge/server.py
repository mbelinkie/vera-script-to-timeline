"""Private MCP server for VERA Mac Bridge; launched by OpenAI tunnel-client via stdio."""

from mcp.server import MCPServer
from shell_core import mac_exec_local

mcp = MCPServer("VERA Mac Shell")


@mcp.tool()
def mac_health() -> dict:
    """Return bridge liveness without executing Terminal commands."""
    return {"status": "ok", "service": "vera-mac-shell", "version": "0.1.0", "approval": "on-mac-per-command"}


@mcp.tool()
def mac_exec(command: str, cwd: str = "vera", timeout_seconds: int = 25) -> dict:
    """Request a Terminal command. Requires the Producer to click Run once on their Mac.

    command: A single line of shell syntax (max 240 characters) shown verbatim on Mac.
    cwd: 'vera' (locally configured repo) or 'home'.
    timeout_seconds: Execution cap between 1 and 35 seconds.

    Every invocation can read/write local files or use the network *if locally
    approved*. Don't call with secrets in the command or without user intent.
    """
    return mac_exec_local(command, cwd, timeout_seconds)


if __name__ == "__main__":
    mcp.run()
