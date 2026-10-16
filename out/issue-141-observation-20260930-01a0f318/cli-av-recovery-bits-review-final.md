Updated the fresh recovery XML guard in [av-output.py](../../docs/investigations/issue-141/av-output.py) to accept only original LPCM bit depths 16 or 24, and record the original depth in the audit. Render job metadata and output media still require PCM24.

Added focused fake cases in [av-output-check.py](../../docs/investigations/issue-141/av-output-check.py). The check passed: original PCM16 proceeds, PCM20 refuses, and the existing checks retain the PCM24 job/output requirement. Recorded the hashes and result in the ignored readiness JSON.

A fresh checkpoint and uniquely named recovery export are still required; the historical PCM16 preset is not reusable. No Resolve, Hammerspoon, config, or native dispatch was used.