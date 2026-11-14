from hashlib import sha256
from pathlib import Path

from huggingface_hub import snapshot_download

model_dir = Path('/opt/models')
snapshot_download(
    repo_id='ResembleAI/resemble-enhance',
    revision='cd13fe403de7b3150495a79418edfb38eb9562a5',
    local_dir=model_dir,
    allow_patterns=['enhancer_stage2/hparams.yaml', 'enhancer_stage2/ds/G/latest',
                    'enhancer_stage2/ds/G/default/mp_rank_00_model_states.pt'],
)
weights = model_dir / 'enhancer_stage2/ds/G/default/mp_rank_00_model_states.pt'
hasher = sha256()
with weights.open('rb') as stream:
    for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
        hasher.update(chunk)
digest = hasher.hexdigest()
expected = 'f9d035f318de3e6d919bc70cf7ad7d32b4fe92ec5cbe0b30029a27f5db07d9d6'
if digest != expected:
    raise SystemExit(f'unexpected model SHA-256: {digest}')
print(f'checkpoint SHA-256: {digest}', flush=True)
