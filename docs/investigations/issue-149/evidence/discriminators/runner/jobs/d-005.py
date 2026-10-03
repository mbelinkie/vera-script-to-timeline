JOB_ID = 'd-005-console-mute-in-codex-project'
exec(open(RUNNER_DIR + '/lib_snap.py').read()); exec(open(RUNNER_DIR + '/lib_build.py').read()); exec(open(RUNNER_DIR + '/lib_disc.py').read())
import json as _j
pm = resolve.GetProjectManager(); pr = pm.GetCurrentProject(); mp = pr.GetMediaPool()
RESULT['project'] = pr.GetName()
assert pr.GetName() == 'VERA Issue 149 WI Discriminators 20261003-kit-02', pr.GetName()
assert not pr.IsRenderingInProgress(), 'render still running'
J = []; Q = []
def walk(f, acc):
    for c in f.GetClipList(): acc.setdefault(c.GetName(), c)
    for s in f.GetSubFolderList(): walk(s, acc)
    return acc
P = walk(mp.GetRootFolder(), {}); J.append({'pool': sorted(P)})
pool_by_name = lambda _mp: P   # build() uses the recursive pool
T = tls_by_name(pr); J.append({'timelines': sorted(T)})
src = T['D3-direct-av-20261003']
J.append({'codex_A2_now': src.GetItemListInTrack('audio', 2)[0].GetSourceAudioChannelMapping()})
J.append({'render_format': js(pr.GetCurrentRenderFormatAndCodec())})
resolve.OpenPage('edit')
# C1: duplicate of Codex's D3-direct timeline, muted from the Console
pr.SetCurrentTimeline(src)
dup = src.DuplicateTimeline('CLAUDE C1 dup D3-direct console mute')
J.append({'dup': js(dup)})
# C2: fresh timeline built in Codex's project from its own pool items, muted from the Console
mspec = [{'name':'base.mov','src':(0,400),'rec':0,'track':1}, {'name':'a2_numbers.wav','src':(0,400),'rec':0,'track':2,'media':'a'}, {'name':'a3_bed.wav','src':(0,400),'rec':0,'track':3,'media':'a'}]
c2, _ = build(pr, mp, 'CLAUDE C2 fresh console mute', mspec, J)
for t, k in ((dup, 'C1'), (c2, 'C2')):
    J.append({k + ' tracks': [t.GetTrackCount('audio')] + [t.GetTrackSubType('audio', i) for i in range(1, t.GetTrackCount('audio') + 1)]})
    J.append({k + ' mute': mute_a2(t)})
for t, tag in ((dup, 'C1_codexproj_dup_console_mute'), (c2, 'C2_codexproj_fresh_console_mute')):
    Q.append(queue(pr, t, tag))
J.append(['StartRendering', js(call(pr, 'StartRendering', [q[2] for q in Q]))])
RESULT.update({'journal': J, 'queue': Q})
