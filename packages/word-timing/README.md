# VERA word timing

`vera-word-timing` runs the shared recognition and alignment pipeline. Run
`vera-word-timing --help` for the command list.

## Cancel local alignment

On macOS and Linux, pass `--cancel-file` to opt in for one alignment job.

```sh
vera-word-timing align --audio input.wav --recognition recognition.json \
  --out alignment.json --cancel-file /path/to/job/cancel
```

Use a unique, initially absent path in the job's scratch directory. To cancel,
create an empty file at that path and leave it there until the CLI exits. A
marker already present at startup cancels before the CLI opens the inputs. Wait
for the CLI to exit and read the JSON it writes to stdout:

| Result | What the caller can conclude |
| --- | --- |
| Exit 3, `port-refusal/v1` with `port: "aligner"` and `code: "cancelled"` | All engine processes in this invocation's process groups have stopped. The invocation has released any MFA lock it acquired. The caller can remove job scratch. |
| Exit 3, `port-refusal/v1` with `port: "aligner"` and `code: "shutdown-unconfirmed"` | The CLI could not verify engine shutdown. Keep job scratch and require separate confirmation before cleaning up or retrying. |
| Exit 0 | Alignment completed. Read the normal alignment artifact, from `--out` if supplied. |

Cancellation writes no alignment artifact and leaves an existing `--out` file
untouched. If the CLI is killed, crashes, or exits without either documented
cancellation record after a request, the caller has no cancellation
acknowledgment. Sending an OS signal to the CLI is outside this contract.

The CLI checks the marker about every 100 ms during an engine wait or MFA lock
wait. A launch or input read already in progress must return before the next
check. An active engine gets up to 15 seconds to stop on SIGTERM and 10 more
seconds after SIGKILL. Configured local engines must keep their children in the
engine's process group for the CLI to supervise them. Opting in selects SQLite
for MFA so it does not launch a detached PostgreSQL server. A group still
visible at the deadline is unconfirmed, including when the OS has yet to reap
an exited child.
