# VERA 141 second-opinion runner. Launched from Resolve's Console with one exec() line.
# Executes runner/job.py with the injected `resolve`, captures result/errors to results/<job_id>.json.
import json, time, traceback, io, contextlib, os
_R = '~/Desktop/ONGOING/VERA Script to Timeline/out/issue-141-second-opinion/runner'
_src = open(_R + '/job.py').read()
_g = {'resolve': resolve, '__name__': '__vera_job__', 'RESULT': {}, 'RUNNER_DIR': _R}
_out = io.StringIO(); _err = None; _t0 = time.time()
try:
    with contextlib.redirect_stdout(_out):
        exec(compile(_src, 'job.py', 'exec'), _g)
except Exception:
    _err = traceback.format_exc()
_job = _g.get('JOB_ID', 'unnamed')
_rec = {'job_id': _job, 'started': _t0, 'seconds': round(time.time() - _t0, 3),
        'error': _err, 'stdout': _out.getvalue()[-20000:], 'result': _g.get('RESULT')}
with open('%s/results/%s.json' % (_R, _job), 'w') as f:
    json.dump(_rec, f, indent=1, default=repr)
print('VERA runner finished', _job, 'error' if _err else 'ok')
