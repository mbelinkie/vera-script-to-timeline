# Console render — Issue #149

**Status: completed and collected. Do not execute this command again.**

The WI mute-only pair and Console configuration passed independent staging review. This case has not rendered. Run this step once; a reported error is evidence to retain, not a reason to retry.

1. In project **VERA Issue 149 WI Discriminators 20261003-kit-02**, confirm timeline **D3-console-av-20261003** is current.
2. Open **Workspace → Console** and select **Python 3**.
3. Paste the following command and press Enter once. Leave mapping, M/S, clips and playhead unchanged.

```python
exec(compile(open("REPOSITORY/docs/investigations/issue-149/workflow-discriminators/console-render.py", encoding="utf-8").read(), "REPOSITORY/docs/investigations/issue-149/workflow-discriminators/console-render.py", "exec"), dict(globals(), __file__="REPOSITORY/docs/investigations/issue-149/workflow-discriminators/console-render.py", CONSOLE_CONFIG_PATH="REPOSITORY/out/issue149-workflow-discriminators-20261003-kit-02/params/d3-console-render.json"))
```

Reply **ran** when it finishes, or provide the error text. Do not run the command twice. No Fairlight action is requested yet.

The original wrapper failed while decoding the source with ASCII, before helper execution. Explicit UTF-8 decoding is now supplied. Independent local decoding/compile and a fresh complete native observation verified unchanged source/config hashes, no receipt/job, and unchanged staged mute state. This is the first actual helper execution for the same bounded action, not a render replay.
