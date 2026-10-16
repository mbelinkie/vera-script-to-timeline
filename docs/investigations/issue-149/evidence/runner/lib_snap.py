# Snapshot helpers: raw getter values (or 'ERR ...'), never defaulted.
import json, hashlib
def call(o, m, *a):
    try:
        f = getattr(o, m)
    except Exception as e:
        return 'NOATTR %r' % e
    try:
        return f(*a)
    except Exception as e:
        return 'ERR %r' % e
def js(x):
    try: return json.loads(json.dumps(x, default=repr))
    except Exception: return repr(x)
ITEM_GETTERS = ['GetName','GetUniqueId','GetStart','GetEnd','GetDuration','GetLeftOffset','GetRightOffset',
  'GetSourceStartFrame','GetSourceEndFrame','GetSourceStartTime','GetSourceEndTime','GetClipEnabled','GetSpeed',
  'GetMarkers','GetFlagList','GetClipColor','GetSourceAudioChannelMapping','GetVoiceIsolationState','GetTrackTypeAndIndex']
def item_snap(it):
    d = {g: js(call(it, g)) for g in ITEM_GETTERS}
    for g in ('GetStart','GetEnd','GetDuration','GetLeftOffset','GetRightOffset'):
        d[g + '(True)'] = js(call(it, g, True))
    d['GetProperty()'] = js(call(it, 'GetProperty'))
    mpi = call(it, 'GetMediaPoolItem')
    d['mpi_uid'] = js(call(mpi, 'GetUniqueId')) if mpi and not isinstance(mpi, str) else js(mpi)
    li = call(it, 'GetLinkedItems')
    d['linked_uids'] = [js(call(x, 'GetUniqueId')) for x in li] if isinstance(li, list) else js(li)
    return d
def timeline_snap(tl, project=None):
    s = {'name': call(tl,'GetName'), 'uid': call(tl,'GetUniqueId'), 'start_frame': call(tl,'GetStartFrame'),
         'end_frame': call(tl,'GetEndFrame'), 'start_tc': call(tl,'GetStartTimecode'),
         'mark_in_out': js(call(tl,'GetMarkInOut')), 'markers': js(call(tl,'GetMarkers')), 'tracks': {}}
    if project is not None:
        cur = call(project, 'GetCurrentTimeline'); s['is_current'] = (call(cur,'GetUniqueId') == s['uid']) if cur else False
    for tt in ('video','audio','subtitle'):
        n = call(tl, 'GetTrackCount', tt); s['tracks'][tt] = []
        if not isinstance(n, int): continue
        for i in range(1, n+1):
            tr = {'index': i, 'name': call(tl,'GetTrackName',tt,i), 'enabled': call(tl,'GetIsTrackEnabled',tt,i),
                  'locked': call(tl,'GetIsTrackLocked',tt,i)}
            if tt == 'audio':
                tr['subtype'] = call(tl,'GetTrackSubType',tt,i); tr['voice_iso'] = js(call(tl,'GetVoiceIsolationState',i))
            items = call(tl, 'GetItemListInTrack', tt, i)
            tr['items'] = [item_snap(it) for it in items] if isinstance(items, list) else js(items)
            s['tracks'][tt].append(tr)
    return s
def pool_snap(mp):
    out = []
    def walk(folder, path):
        for c in (call(folder,'GetClipList') or []):
            out.append({'path': path, 'name': call(c,'GetName'), 'uid': call(c,'GetUniqueId'),
                        'props': js(call(c,'GetClipProperty')), 'mark_in_out': js(call(c,'GetMarkInOut')),
                        'audio_mapping': js(call(c,'GetAudioMapping'))})
        for sub in (call(folder,'GetSubFolderList') or []): walk(sub, path + '/' + str(call(sub,'GetName')))
    walk(mp.GetRootFolder(), ''); return out
def fingerprint(x): return hashlib.sha256(json.dumps(x, sort_keys=True, default=repr).encode()).hexdigest()
def full_snap(resolve):
    pm = resolve.GetProjectManager(); pr = pm.GetCurrentProject(); mp = pr.GetMediaPool()
    tls = [pr.GetTimelineByIndex(i) for i in range(1, pr.GetTimelineCount()+1)]
    s = {'page': call(resolve,'GetCurrentPage'), 'project': call(pr,'GetName'), 'project_uid': call(pr,'GetUniqueId'),
         'current_timeline': call(call(pr,'GetCurrentTimeline'),'GetUniqueId') if pr.GetCurrentTimeline() else None,
         'timelines': [timeline_snap(t, pr) for t in tls], 'pool': pool_snap(mp)}
    s['fingerprint'] = fingerprint({k: v for k, v in s.items() if k != 'page'}); return s
