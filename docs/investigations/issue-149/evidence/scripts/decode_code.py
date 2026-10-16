"""Decode the (src_id, frame) block code from video frames. Usage: decode_code.py <video> [scale_w scale_h]"""
import subprocess, sys, numpy as np
def frames(path, w=640, h=360):
    p = subprocess.Popen(['ffmpeg','-v','error','-i',path,'-vf',f'scale={w}:{h}:flags=neighbor','-f','rawvideo','-pix_fmt','gray','-'], stdout=subprocess.PIPE)
    while True:
        b = p.stdout.read(w*h)
        if len(b) < w*h: break
        yield np.frombuffer(b, np.uint8).reshape(h, w)
def decode(img):
    h, w = img.shape; bw = w / 16; y = int(16 * h / 360)
    bits = [1 if img[y, int(bw*b + bw/2)] > 128 else 0 for b in range(16)]
    v = 0
    for b in bits: v = (v << 1) | b
    return v >> 12, v & 0xFFF
if __name__ == '__main__':
    out = [decode(f) for f in frames(sys.argv[1])]
    print(len(out), out[:3], out[123], out[-1])
