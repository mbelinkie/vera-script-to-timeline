"""Structural visibility predictor vs decoded render. Predict only when the topmost enabled item at a frame is
opaque video with no transform/opacity change; otherwise 'needs-render'."""
import json, sys, os, numpy as np
sys.path.insert(0, os.path.dirname(__file__)); from decode_code import frames, decode
snap = json.load(open(sys.argv[1]))['result']['snap']; render = sys.argv[2]
SRC = {'base.mov': 1, 'cutaway.mov': 2}
items = []
for tr in snap['tracks']['video']:
    for it in tr['items']:
        p = it['GetProperty()'] if isinstance(it['GetProperty()'], dict) else {}
        items.append({'track': tr['index'], 'name': it['GetName'], 's': it['GetStart'], 'e': it['GetEnd'], 'src0': it['GetSourceStartFrame'],
                      'enabled': it['GetClipEnabled'], 'opacity': p.get('Opacity'), 'zx': p.get('ZoomX'), 'zy': p.get('ZoomY'),
                      'mode': p.get('CompositeMode'), 'track_enabled': tr['enabled']})
def predict(f):
    cover = [i for i in items if i['s'] <= f < i['e'] and i['enabled'] is True]
    if not cover: return ('black', None)
    top = max(cover, key=lambda i: i['track'])
    simple = top['name'] in SRC and top['opacity'] in (100.0, None) and top['zx'] in (1.0, None) and top['zy'] in (1.0, None) and top['mode'] in (0, None)
    if not simple: return ('needs-render', top['name'])
    return ('predict', (SRC[top['name']], top['src0'] + (f - top['s'])))
got = [decode(x) for x in frames(render)]
stats = {'predict_match': 0, 'predict_mismatch': 0, 'needs_render': 0, 'black': 0}; bad = []; nr = {}
for f, g in enumerate(got):
    k, v = predict(f)
    if k == 'predict':
        if v == g: stats['predict_match'] += 1
        else: stats['predict_mismatch'] += 1; bad.append((f, v, g))
    elif k == 'needs-render': stats['needs_render'] += 1; nr.setdefault(v, []).append((f, g))
    else: stats['black'] += 1
print('frames', len(got), stats); print('mismatches', bad[:10])
for n, lst in nr.items(): print('needs-render under', n, 'decoded examples', lst[:3], '...', sorted(set(x[1][0] for x in lst)))
print('items', [(i['track'], i['name'], i['s'], i['e'], i['enabled'], i['opacity'], i['zx']) for i in items])
