JOB_ID = 'd-003-queue-order-page-settings-and-relink'
exec(open(RUNNER_DIR + '/lib_snap.py').read()); exec(open(RUNNER_DIR + '/lib_build.py').read()); exec(open(RUNNER_DIR + '/lib_disc.py').read())
pm = resolve.GetProjectManager(); pr = pm.GetCurrentProject(); mp = pr.GetMediaPool()
assert pr.GetName() == 'VERA 149 Discriminators 20261002-b'
assert not pr.IsRenderingInProgress(), 'render still running'
prior = {j.get('RenderJobName', '') + ' ' + j.get('OutputFilename', ''): js(call(pr, 'GetRenderJobStatus', j['JobId'])) for j in (pr.GetRenderJobList() or [])}
resolve.OpenPage('edit')
mspec = [{'name':'base.mov','src':(0,400),'rec':0,'track':1}, {'name':'a2_numbers.wav','src':(0,400),'rec':0,'track':2,'media':'a'}, {'name':'a3_bed.wav','src':(0,400),'rec':0,'track':3,'media':'a'}]
J = []; Tn = {}
for n in ('M_d job added before mute', 'M_e mute on Deliver page', 'M_f mute with Codex render settings'):
    Tn[n], _ = build(pr, mp, n, mspec, J)
call(pr, 'DeleteAllRenderJobs')
Q = []
# M_d: AddRenderJob first (unmuted), then mute, start later
Q.append(queue(pr, Tn['M_d job added before mute'], 'Md_job_added_before_mute'))
J.append(['M_d mute after AddRenderJob', mute_a2(Tn['M_d job added before mute'])])
# M_e: mute while on Deliver page
pr.SetCurrentTimeline(Tn['M_e mute on Deliver page']); resolve.OpenPage('deliver'); J.append(['page', resolve.GetCurrentPage()])
J.append(['M_e mute on deliver', mute_a2(Tn['M_e mute on Deliver page'])]); resolve.OpenPage('edit')
Q.append(queue(pr, Tn['M_e mute on Deliver page'], 'Me_muted_on_deliver'))
# M_f: mute, then Codex-like settings
J.append(['M_f mute', mute_a2(Tn['M_f mute with Codex render settings'])])
pr.SetCurrentTimeline(Tn['M_f mute with Codex render settings'])
J.append(['SetRenderMode 1', js(call(pr, 'SetRenderMode', 1))])
s = {'SelectAllFrames': False, 'MarkIn': 0, 'MarkOut': 398, 'TargetDir': D + '/renders', 'CustomName': 'Mf_muted_codex_settings', 'ExportVideo': True, 'ExportAudio': True,
     'FormatWidth': 640, 'FormatHeight': 360, 'FrameRate': 25.0, 'AudioCodec': 'lpcm', 'AudioSampleRate': 48000, 'AudioBitDepth': 16}
J.append(['M_f settings', js(call(pr, 'SetRenderSettings', s))]); Q.append(['Mf_muted_codex_settings', True, call(pr, 'AddRenderJob')])
# Relink the four swapped files, then render
T = tls_by_name(pr); P = pool(mp)
for n in RCASES:
    J.append(['RelinkClips ' + n, js(call(mp, 'RelinkClips', [P[n + '.mov']], D + '/relink2'))])
    Q.append(queue(pr, T['R_' + n], 'R_%s_3_after_relink' % n, full=False))
J.append(['StartRendering', js(call(pr, 'StartRendering', [q[2] for q in Q]))])
RESULT.update({'prior_render_status': prior, 'journal': J, 'queue': Q})
