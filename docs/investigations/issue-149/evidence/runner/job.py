JOB_ID = 'p5-snap'
exec(open(RUNNER_DIR + '/lib_snap.py').read()); exec(open(RUNNER_DIR + '/lib_lin.py').read())
pm = resolve.GetProjectManager(); pr = pm.GetCurrentProject(); mp = pr.GetMediaPool(); tl = pr.GetCurrentTimeline()
LABEL = open(RUNNER_DIR + '/label.txt').read().strip(); JOB_ID = 'p5-snap-' + LABEL
sel = call(tl, 'GetSelectedClips')
RESULT.update({'label': LABEL, 'current': tl.GetName(), 'playhead': call(tl,'GetCurrentTimecode'), 'selected': [call(x,'GetUniqueId') for x in sel] if isinstance(sel, list) else js(sel),
               'snap': lin_snap(pr, tl), 'pool_marks': pool_marks(mp), 'tl_markinout': js(call(tl,'GetMarkInOut'))})
