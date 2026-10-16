JOB_ID = 'd-004-handle-and-literal-json'
exec(open(RUNNER_DIR + '/lib_snap.py').read()); exec(open(RUNNER_DIR + '/lib_build.py').read()); exec(open(RUNNER_DIR + '/lib_disc.py').read())
import json as _j
pm = resolve.GetProjectManager(); pr = pm.GetCurrentProject()
if pr.GetName() == 'VERA Issue 149 WI Discriminators 20261003-kit-02':
    assert not pr.IsRenderingInProgress(), 'codex project still rendering'
    RESULT['codex_project_claude_jobs'] = {j: js(pr.GetRenderJobStatus(j)) for j in ('5e8136ce-30e7-4120-a861-edd25a627761', '6823f50a-e86b-44aa-9661-852fab143db9')}
    RESULT['save_codex'] = js(pm.SaveProject())
    RESULT['load_mine'] = js(pm.LoadProject('VERA 149 Discriminators 20261002-b'))
    pr = pm.GetCurrentProject()
mp = pr.GetMediaPool()
RESULT['project'] = pr.GetName()
assert pr.GetName() == 'VERA 149 Discriminators 20261002-b', pr.GetName()
assert not pr.IsRenderingInProgress(), 'render still running'
resolve.OpenPage('edit')
mspec = [{'name':'base.mov','src':(0,400),'rec':0,'track':1}, {'name':'a2_numbers.wav','src':(0,400),'rec':0,'track':2,'media':'a'}, {'name':'a3_bed.wav','src':(0,400),'rec':0,'track':3,'media':'a'}]
J = []; Q = []
CODEX_LITERAL = '{"embedded_audio_channels":1,"linked_audio":{},"track_mapping":{"1":{"channel_idx":[1],"mute":true,"type":"mono"}}}'
# H1: mute through the handle AppendToTimeline returned (never re-fetched)
t1, out1 = build(pr, mp, 'H1 mute via append handle', mspec, J)
h_app = out1[1][0]; h_fresh = t1.GetItemListInTrack('audio', 2)[0]
m = _j.loads(h_app.GetSourceAudioChannelMapping()); m['track_mapping']['1']['mute'] = True
J.append({'H1': {'uid_append': h_app.GetUniqueId(), 'uid_fresh': h_fresh.GetUniqueId(),
   'set_via_append': js(h_app.SetSourceAudioChannelMapping(_j.dumps(m))),
   'readback_append': h_app.GetSourceAudioChannelMapping(), 'readback_fresh': h_fresh.GetSourceAudioChannelMapping(),
   'readback_refetch': t1.GetItemListInTrack('audio', 2)[0].GetSourceAudioChannelMapping()}})
# H2: fresh handle, exact compact JSON literal from the Workflow Integration readback
t2, _ = build(pr, mp, 'H2 mute via Codex literal', mspec, J)
h2 = t2.GetItemListInTrack('audio', 2)[0]
J.append({'H2': {'before': h2.GetSourceAudioChannelMapping(), 'set': js(h2.SetSourceAudioChannelMapping(CODEX_LITERAL)), 'readback': h2.GetSourceAudioChannelMapping()}})
# H0: control, unmuted fresh timeline
t0, _ = build(pr, mp, 'H0 unmuted control', mspec, J)
call(pr, 'DeleteAllRenderJobs')
for t, tag in ((t1, 'H1_append_handle_mute'), (t2, 'H2_codex_literal_mute'), (t0, 'H0_unmuted_control')):
    Q.append(queue(pr, t, tag))
J.append({'format': js(pr.GetCurrentRenderFormatAndCodec())})
J.append(['StartRendering', js(call(pr, 'StartRendering', [q[2] for q in Q]))])
RESULT.update({'journal': J, 'queue': Q})
