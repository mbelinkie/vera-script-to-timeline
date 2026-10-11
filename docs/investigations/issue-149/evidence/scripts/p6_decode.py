import sys, glob, os, numpy as np
sys.path.insert(0, os.path.dirname(__file__)); from decode_code import decode, frames
from PIL import Image
for f in sorted(glob.glob(sys.argv[1] + '/stills6/*.png')):
    im = np.array(Image.open(f).convert('L').resize((640, 360), Image.NEAREST)); print('still ', os.path.basename(f), decode(im))
for f in sorted(glob.glob(sys.argv[1] + '/renders6/*.mov')):
    fr = [decode(x) for x in frames(f)]; print('render', os.path.basename(f), len(fr), 'frames; codes', sorted(set(fr))[:3], '... first', fr[:1], 'last', fr[-1:])
