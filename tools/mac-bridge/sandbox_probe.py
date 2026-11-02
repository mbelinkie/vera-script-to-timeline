"""Local-only Seatbelt feasibility probe for issue #400.

This probe intentionally runs only /usr/bin/true and /bin/zsh echo.
It does NOT attempt shell commands supplied by a ChatGPT caller.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

SYSTEM = ["/System", "/usr", "/bin", "/sbin", "/Library"]
EXTRA = [
    "/private/var/db", "/private/etc", "/private/var/folders",
    "/dev", "/private/tmp", "/private/var", "/opt", "/usr/local",
]

def quote(path: str) -> str:
    return '"' + path.replace("\\", "\\\\").replace('"', '\\"') + '"'

def run(profile: str, exe: str = "/usr/bin/true", argv=()) -> int:
    try:
        p = subprocess.run(["/usr/bin/sandbox-exec", "-p", profile, exe, *argv],
                           cwd="/", capture_output=True, timeout=4, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return -999
    return p.returncode

def profile(paths: list[str], *, metadata: bool = False, homedir: bool = False, capabilities: bool = False) -> str:
    lines = ["(version 1)", "(deny default)",
             "(allow process* mach* sysctl*)"]
    if capabilities:
        lines += ["(allow system-mac-syscall)"]
    if metadata:
        lines += ['(allow file-read* file-test-existence (literal "/"))']
    if homedir:
        home = Path.home()
        for ancestor in [*home.parents, home]:
            lines += [f"(allow file-read-metadata file-test-existence (literal {quote(str(ancestor))}))"]
    lines += [
        "(allow file-read* file-test-existence "
        + " ".join("(subpath " + quote(x) + ")" for x in paths)
        + ")"
    ]
    return "\n".join(lines)

def main() -> None:
    if sys.platform != "darwin":
        raise SystemExit("requires macOS")
    cases = [
      ("all_read", "(version 1)(deny default)(allow process* mach* sysctl* file-read* file-test-existence)"),
      ("system", profile(SYSTEM)),
      ("system+root", profile(SYSTEM,metadata=True)),
      ("system+var_db", profile(SYSTEM+EXTRA[:1],metadata=True)),
      ("system+etc", profile(SYSTEM+EXTRA[:2],metadata=True)),
      ("system+var_folders", profile(SYSTEM+EXTRA[:3],metadata=True)),
      ("system+dev", profile(SYSTEM+EXTRA[:4],metadata=True)),
      ("system+tmp", profile(SYSTEM+EXTRA[:5],metadata=True)),
      ("system+var", profile(SYSTEM+EXTRA[:6],metadata=True)),
      ("system+opt", profile(SYSTEM+EXTRA[:7],metadata=True)),
      ("system+local", profile(SYSTEM+EXTRA,metadata=True)),
      ("system+all+homemeta", profile(SYSTEM+EXTRA,metadata=True,homedir=True)),
      ("system+all+systemmac", profile(SYSTEM+EXTRA,metadata=True,homedir=True,capabilities=True)),
    ]
    for name, text in cases:
        print(name, "true:", run(text), "zsh:", run(text, "/bin/zsh", ["-f","-c","echo ok"]))
    for name, caps in [
        ("process+sysctl", "process* sysctl*"),
        ("process+sysctl+lookup", "process* sysctl* mach-lookup"),
        ("minimal+lookup", "process-exec process-fork sysctl-read mach-lookup"),
        ("minimal", "process-exec process-fork sysctl-read"),
    ]:
        text = profile(SYSTEM, metadata=True)
        text = text.replace("(allow process* mach* sysctl*)", f"(allow {caps})")
        print(name, "true:", run(text), "zsh:", run(text, "/bin/zsh", ["-f","-c","echo ok"]))
if __name__ == "__main__":
    main()
