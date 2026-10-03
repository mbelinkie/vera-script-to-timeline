import hashlib, os
B = RUNNER_DIR.rsplit('/runner',1)[0]
SWAP = B + '/fixtures/relink/swap.mov'
def find_item(mp, name):
    for c in mp.GetRootFolder().GetClipList():
        if c.GetName() == name: return c
def p6_capture(pr, tl, item, tag, render=True):
    pr.SetCurrentTimeline(tl); resolve.OpenPage('edit')
    out = {'tag': tag, 'file_sha256': hashlib.sha256(open(SWAP,'rb').read()).hexdigest(), 'file_size': os.path.getsize(SWAP),
           'props': {k: v for k, v in (call(item,'GetClipProperty') or {}).items() if k in ('File Path','Date Modified','Date Created','File Name','Frames','Duration','Online Status','Resolution','Video Codec','Clip Color','Proxy','Optimized Media')}}
    out['set_tc'] = js(call(tl, 'SetCurrentTimecode', '00:00:00:10'))
    out['still'] = js(call(pr, 'ExportCurrentFrameAsStill', '%s/stills6/%s.png' % (B, tag)))
    s = {'SelectAllFrames': False, 'MarkIn': 0, 'MarkOut': 24, 'TargetDir': B + '/renders6', 'CustomName': tag, 'ExportVideo': True, 'ExportAudio': True,
         'FormatWidth': 640, 'FormatHeight': 360, 'ExportSubtitle': False}
    if not render: return out
    call(pr, 'DeleteAllRenderJobs'); out['render_settings'] = js(call(pr, 'SetRenderSettings', s))
    jid = call(pr, 'AddRenderJob'); out['render_start'] = js(call(pr, 'StartRendering', [jid]))
    return out
