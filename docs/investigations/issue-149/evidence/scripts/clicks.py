"""Find rendered impulse positions and compare with source clicks / speed."""
import json, subprocess, sys, numpy as np
SR = 48000
man = json.load(open(sys.argv[1]))['files']['clicks.wav']['impulse_samples']
def load(p):
    raw = subprocess.run(['ffmpeg','-v','error','-i',p,'-map','0:a:0','-ar',str(SR),'-f','f32le','-'], capture_output=True, check=True).stdout
    ch = int(subprocess.run(['ffprobe','-v','error','-select_streams','a:0','-show_entries','stream=channels','-of','csv=p=0',p], capture_output=True, text=True).stdout.strip().split('\n')[0])
    return np.frombuffer(raw, np.float32).reshape(-1, ch)
for p, speed in zip(sys.argv[2::2], sys.argv[3::2]):
    sp = float(speed) / 100; x = load(p)
    a = np.abs(x).max(axis=1)
    # local maxima above threshold, after removing the low-level speech/pilot (base A1 is ~0.8 peak, so use sharpness: sample >> neighbours)
    cand = np.nonzero(a > 0.3)[0]
    peaks = []
    for c in cand:
        if peaks and c - peaks[-1] < 200: 
            if a[c] > a[peaks[-1]]: peaks[-1] = c
            continue
        peaks.append(int(c))
    pred = [s / sp for s in man if s / sp < len(a)]
    rows = []
    for q in pred:
        near = min(peaks, key=lambda k: abs(k - q)) if peaks else None
        rows.append((round(q, 2), near, None if near is None else round(near - q, 2)))
    print(p, 'samples', len(a), 'peaks', len(peaks), 'predicted', len(pred))
    for r in rows: print('   pred %10.2f  found %8s  diff %s' % r)
