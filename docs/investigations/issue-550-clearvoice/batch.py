import hashlib
import time
from pathlib import Path
import numpy as np
import soundfile as sf
from clearvoice import ClearVoice

model = ClearVoice(task='speech_enhancement', model_names=['MossFormer2_SE_48K'])
for source in sorted(Path('/input').glob('*-original.wav')):
    target = Path('/output') / source.name.replace('-original', '-clearvoice')
    if target.exists():
        raise SystemExit(f'refusing to overwrite {target}')
    start = time.monotonic()
    audio, rate = sf.read(source, dtype='float32')
    result = model(input_path=str(source), online_write=False)
    if isinstance(result, (tuple, list)) and len(result) == 1:
        result = result[0]
    if isinstance(result, dict) and len(result) == 1:
        result = next(iter(result.values()))
    result = np.asarray(result, dtype=np.float32).squeeze()
    sf.write(target, result, rate, subtype='PCM_24')
    peak = Path('/sys/fs/cgroup/memory.peak').read_text().strip()
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    print(f'{source.name} input={audio.size} output={result.size} rate={rate} elapsed={time.monotonic()-start:.2f} peak={peak} sha256={digest}', flush=True)
