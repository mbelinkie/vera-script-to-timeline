# Build test timelines by placement (for transcript/output tests only; editorial-identity tests use real UI edits).
def pool_by_name(mp):
    return {call(c,'GetName'): c for c in mp.GetRootFolder().GetClipList()}
def build(pr, mp, name, placements, J):
    """placements: list of dicts {name, src:(a,b) frames half-open, rec, track, media: 'av'|'v'|'a'}"""
    P = pool_by_name(mp)
    tl = mp.CreateEmptyTimeline(name); pr.SetCurrentTimeline(tl); tl.SetStartTimecode('00:00:00:00')
    tl.AddTrack('audio','mono'); tl.AddTrack('audio','mono'); tl.AddTrack('video'); tl.AddTrack('video')
    out = []
    for p in placements:
        ci = {'mediaPoolItem': P[p['name']], 'startFrame': p['src'][0], 'endFrame': p['src'][1] - 1,
              'trackIndex': p['track'], 'recordFrame': p['rec']}
        if p.get('media') == 'v': ci['mediaType'] = 1
        if p.get('media') == 'a': ci['mediaType'] = 2
        r = mp.AppendToTimeline([ci]); J.append({'op': 'append %s %s' % (name, p), 'ret': js(r)}); out.append(r)
    return tl, out
