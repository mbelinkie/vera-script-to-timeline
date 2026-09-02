"""Hold one local writer lock until the Node parent's pipe closes. No cleanup."""

import fcntl
import os
import sys

descriptor = os.open(sys.argv[1], os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
try:
    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    sys.exit(2)
print("locked", flush=True)
sys.stdin.read()
