"""For each rendered file: which of the 16 words are present (normalized xcorr peak + position) and pilot-tone levels."""
import json, subprocess, sys, os, glob, numpy as np
SR = 48000
FX = sys.argv[1]; files = sys.argv[2:]
man = json.load(open(os.path.join(FX, 'manifest.json')))
def load(p, ch=None):
    raw = subprocess.run(['ffmpeg','-v','error','-i',p,'-ac','1','-ar',str(SR),'-f','f32le','-'], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(np.float64)
src = {'a1_alpha.wav': load(os.path.join(FX,'a1_alpha.wav')), 'a2_numbers.wav': load(os.path.join(FX,'a2_numbers.wav'))}
templates = []
for f in ('a1_alpha.wav','a2_numbers.wav'):
    for w in man['files'][f]['words']:
        t = src[f][w['start_sample']:w['end_sample']].copy(); t -= t.mean(); templates.append((w['word'], f, w['start_sample'], t))
def ncc(x, t):
    n = len(x) + len(t); N = 1 << (n-1).bit_length()
    c = np.fft.irfft(np.fft.rfft(x, N) * np.conj(np.fft.rfft(t, N)), N)[:len(x)-len(t)+1]
    cs = np.concatenate([[0], np.cumsum(x*x)]); e = cs[len(t):] - cs[:-len(t)]
    return c / (np.sqrt(np.maximum(e, 1e-12)) * np.linalg.norm(t))
def pilot(x, hz):
    if len(x) == 0: return 0.0
    tt = np.arange(len(x))/SR; return float(2*np.abs(np.mean(x*np.exp(-2j*np.pi*hz*tt))))
out = {}
for p in files:
    x = load(p); r = {'samples': len(x), 'pilots': {h: round(pilot(x, h), 5) for h in (1000, 1500, 2000)}, 'words': {}}
    for w, f, s0, t in templates:
        c = ncc(x, t); k = int(np.argmax(c))
        r['words'][w] = {'score': round(float(c[k]), 3), 'at_sample': k, 'at_frame': round(k/1920, 3)}
    r['present'] = [w for w, v in r['words'].items() if v['score'] > 0.8]
    out[os.path.basename(p)] = r
print(json.dumps(out, indent=1))
