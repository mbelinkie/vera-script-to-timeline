import torch
import torchaudio
from resemble_enhance.enhancer.inference import load_enhancer

assert torch.__version__ == '2.2.2+cpu', torch.__version__
assert torchaudio.__version__ == '2.2.2+cpu', torchaudio.__version__
assert not torch.cuda.is_available()
load_enhancer('/opt/models/enhancer_stage2', 'cpu')
print('CPU checkpoint loaded', flush=True)
