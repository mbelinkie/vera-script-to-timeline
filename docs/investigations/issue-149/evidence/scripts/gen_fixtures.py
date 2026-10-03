"""Phase 1 fixtures for the VERA 141 second opinion. Deterministic given the say-recorded word AIFFs.
Every track/source identifies itself in output: unique words, unique pilot tone, per-frame source+frame code."""
import json, hashlib, subprocess, sys, os, numpy as np
from PIL import Image, ImageDraw, ImageFont
FX = sys.argv[1]; SR = 48000; FPS = 25; SECONDS = 16; N = SR * SECONDS; FRAMES = FPS * SECONDS
W, H = 640, 360
def load(p):
    raw = subprocess.run(['ffmpeg','-v','error','-i',p,'-ac','1','-ar',str(SR),'-f','s16le','-'], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float64) / 32768
def trim(x, th=0.002):
    nz = np.nonzero(np.abs(x) > th)[0]; return x[nz[0]:nz[-1]+1]
def write_wav(name, x):
    p = os.path.join(FX, name); pcm = (np.clip(x, -1, 1) * 32767).astype('<i2').tobytes()
    subprocess.run(['ffmpeg','-v','error','-y','-f','s16le','-ar',str(SR),'-ac','1','-i','-', p], input=pcm, check=True); return p
def sha(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
t = np.arange(N) / SR
def speech_track(words, first_onset_s, pilot_hz):
    x = 0.02 * np.sin(2*np.pi*pilot_hz*t); sup = []
    for k, w in enumerate(words):
        wav = trim(load(os.path.join(FX, 'words', w + '.aiff')))
        on = int(round((first_onset_s + 2*k) * SR)); x[on:on+len(wav)] += 0.8 * wav / np.max(np.abs(wav))
        sup.append({'word': w, 'start_sample': on, 'end_sample': on + len(wav),
                    'start_frame_float': on / (SR/FPS), 'end_frame_float': (on+len(wav)) / (SR/FPS)})
    return x, sup
manifest = {'sample_rate': SR, 'fps': FPS, 'seconds': SECONDS, 'interval_convention': 'half-open [start,end) samples', 'files': {}}
a1, s1 = speech_track(['alpha','bravo','charlie','delta','echo','foxtrot','golf','hotel'], 0.5, 1000)
a2, s2 = speech_track(['one','two','three','four','five','six','seven','eight'], 1.5, 1500)
a3 = 0.015*np.sin(2*np.pi*110*t) + 0.02*np.sin(2*np.pi*2000*t)
clicks = np.zeros(N); cpos = []
offsets = [1, 777, 959, 1919]
for i, f in enumerate(range(25, FRAMES, 25)):
    pos = f*(SR//FPS) + offsets[i % 4]; clicks[pos] = 0.9; cpos.append(pos)
pa1 = write_wav('a1_alpha.wav', a1); pa2 = write_wav('a2_numbers.wav', a2)
pa3 = write_wav('a3_bed.wav', a3); pcl = write_wav('clicks.wav', clicks)
manifest['files']['a1_alpha.wav'] = {'pilot_hz': 1000, 'words': s1}
manifest['files']['a2_numbers.wav'] = {'pilot_hz': 1500, 'words': s2}
manifest['files']['a3_bed.wav'] = {'pilot_hz': 2000, 'bed_hz': 110}
manifest['files']['clicks.wav'] = {'impulse_samples': cpos, 'amplitude': 0.9}
try: font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 64); small = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 28)
except Exception: font = ImageFont.load_default(64); small = ImageFont.load_default(28)
def frame(src_id, label, bg, f):
    im = Image.new('RGB', (W, H), bg); d = ImageDraw.Draw(im)
    code = (src_id << 12) | f
    for b in range(16):
        bit = (code >> (15 - b)) & 1; d.rectangle([b*40, 0, b*40+39, 31], fill=(255,255,255) if bit else (0,0,0))
    d.text((30, 110), label, font=font, fill=(255,255,255)); d.text((30, 210), 'src %d  frame %04d' % (src_id, f), font=small, fill=(255,255,255))
    return im.tobytes()
def video(name, src_id, label, bg, audio=None):
    p = os.path.join(FX, name)
    cmd = ['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-']
    if audio: cmd += ['-i', audio]
    cmd += ['-c:v','libx264','-g','1','-crf','14','-pix_fmt','yuv420p']
    cmd += (['-c:a','pcm_s16le','-ac','1','-shortest'] if audio else ['-an'])
    pr = subprocess.Popen(cmd + [p], stdin=subprocess.PIPE)
    for f in range(FRAMES): pr.stdin.write(frame(src_id, label, bg, f))
    pr.stdin.close(); assert pr.wait() == 0; return p
pb = video('base.mov', 1, 'BASE', (20, 40, 120), pa1)
pc = video('cutaway.mov', 2, 'CUTAWAY', (200, 90, 10))
ov = Image.new('RGBA', (W, H), (0, 200, 0, 128)); dd = ImageDraw.Draw(ov); dd.text((30, 280), 'OVERLAY', font=small, fill=(255,255,255,255))
po = os.path.join(FX, 'overlay.png'); ov.save(po)
manifest['files']['base.mov'] = {'src_id': 1, 'embedded_audio': 'a1_alpha.wav', 'frames': FRAMES}
manifest['files']['cutaway.mov'] = {'src_id': 2, 'frames': FRAMES}
manifest['files']['overlay.png'] = {'rgba_alpha': 128}
manifest['frame_code'] = 'top 16 blocks of 40x32 px, MSB first, white=1; value=(src_id<<12)|frame'
for n in list(manifest['files']): manifest['files'][n]['sha256'] = sha(os.path.join(FX, n))
json.dump(manifest, open(os.path.join(FX, 'manifest.json'), 'w'), indent=1)
print('ok', {n: manifest['files'][n]['sha256'][:12] for n in manifest['files']})
