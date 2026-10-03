import json, sys, os, glob, subprocess
sys.path.insert(0, os.path.dirname(__file__)); from decode_code import frames, decode
B = sys.argv[1]
out = {}
movs = sorted(glob.glob(B + '/disc/renders/*.mov'))
aud = {}
for m in movs:
    r = subprocess.run(['python3', os.path.dirname(__file__) + '/analyze_audio.py', B + '/fixtures', m], capture_output=True, text=True)
    try: aud.update(json.loads(r.stdout))
    except Exception: aud[os.path.basename(m)] = {'error': 'unreadable'}
for m in movs:
    n = os.path.basename(m); fr = [decode(x) for x in frames(m)]
    a = aud.get(n, {})
    out[n] = {'frames': len(fr), 'src_ids': sorted(set(f[0] for f in fr)), 'first': fr[:1], 'last': fr[-1:], 'pilots': a.get('pilots'),
              'numbers_present': [w for w in a.get('present', []) if w in ('one','two','three','four','five','six','seven','eight')],
              'nato_present': [w for w in a.get('present', []) if w not in ('one','two','three','four','five','six','seven','eight')]}
json.dump(out, open(B + '/disc/analysis.json', 'w'), indent=1)
for n, r in out.items():
    print('%-42s frames %3d src %s pilots %s nato %d numbers %d' % (n, r['frames'], r['src_ids'], r['pilots'], len(r['nato_present']), len(r['numbers_present'])))
