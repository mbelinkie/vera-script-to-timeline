def lin_snap(pr, tl):
    s = timeline_snap(tl, pr); out = []
    for tt in ('video', 'audio'):
        for tr in s['tracks'][tt]:
            for it in tr['items']:
                mk = it['GetMarkers'] or {}
                out.append({'trk': tt[0] + str(tr['index']), 'uid': it['GetUniqueId'], 'name': it['GetName'], 'rec': [it['GetStart'], it['GetEnd']],
                            'src': [it['GetSourceStartFrame'], it['GetSourceEndFrame']], 'mpi': it['mpi_uid'], 'color': it['GetClipColor'],
                            'flags': it['GetFlagList'], 'markers': {str(k): v.get('customData') for k, v in mk.items()} if isinstance(mk, dict) else mk,
                            'linked': it['linked_uids']})
    return {'timeline': s['name'], 'tl_uid': s['uid'], 'items': out}
def pool_marks(mp):
    return {c.GetName(): [js(call(c,'GetMarkInOut')), (call(c,'GetClipProperty') or {}).get('In') if isinstance(call(c,'GetClipProperty'), dict) else None,
                          (call(c,'GetClipProperty') or {}).get('Out') if isinstance(call(c,'GetClipProperty'), dict) else None] for c in mp.GetRootFolder().GetClipList()}
