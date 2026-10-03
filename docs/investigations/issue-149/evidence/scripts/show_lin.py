import json, sys
d = json.load(open(sys.argv[1])); print('error', d['error']); r = d['result']
print(r['label'], r['current'], 'playhead', r['playhead'], 'selected', [u[:8] for u in r['selected']] if isinstance(r['selected'], list) else r['selected'], 'tl markIO', r['tl_markinout'])
for it in r['snap']['items']: print('  ', it['trk'], it['uid'][:8], it['name'], it['rec'], it['src'], it['color'], it['markers'], [u[:8] for u in it['linked']])
print('   pool marks', {k: v for k, v in r['pool_marks'].items() if k in ('base.mov', 'cutaway.mov')})
