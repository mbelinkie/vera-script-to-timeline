import os, hashlib, shutil, time
B = RUNNER_DIR.rsplit('/runner',1)[0]; D = B + '/disc'; FX = B + '/fixtures'
RCASES = ['A_atomic_keepmtime', 'B_atomic_newmtime', 'C_inplace_keepmtime', 'D_inplace_newmtime']
def fstat(p):
    st = os.stat(p); return {'inode': st.st_ino, 'mtime_ns': st.st_mtime_ns, 'size': st.st_size, 'sha256': hashlib.sha256(open(p,'rb').read()).hexdigest()[:16]}
def tls_by_name(pr): return {pr.GetTimelineByIndex(i).GetName(): pr.GetTimelineByIndex(i) for i in range(1, pr.GetTimelineCount()+1)}
def pool(mp): return {c.GetName(): c for c in mp.GetRootFolder().GetClipList()}
def queue(pr, tl, tag, full=True):
    pr.SetCurrentTimeline(tl)
    s = {'TargetDir': D + '/renders', 'CustomName': tag, 'ExportVideo': True, 'ExportAudio': True, 'FormatWidth': 640, 'FormatHeight': 360,
         'AudioSampleRate': 48000, 'AudioBitDepth': 16, 'ExportSubtitle': False}
    if full: s['SelectAllFrames'] = True
    else: s.update({'SelectAllFrames': False, 'MarkIn': 0, 'MarkOut': 24})
    ok = call(pr, 'SetRenderSettings', s); jid = call(pr, 'AddRenderJob')
    return [tag, js(ok), jid]
def mute_a2(tl, value=True):
    import json as _j
    it = tl.GetItemListInTrack('audio', 2)[0]; m = _j.loads(it.GetSourceAudioChannelMapping())
    for k in m.get('track_mapping', {}): m['track_mapping'][k]['mute'] = value
    r = it.SetSourceAudioChannelMapping(_j.dumps(m)); return {'set': js(r), 'readback': it.GetSourceAudioChannelMapping()}
