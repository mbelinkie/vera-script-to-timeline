FROM python:3.10.16-slim-bookworm

ARG RESEMBLE_SOURCE_SHA=8e978149bfe8abab3eb77d965d579a111afdb0ff

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    DS_BUILD_OPS=0 \
    HF_HUB_DISABLE_TELEMETRY=1 \
    HOME=/tmp

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git build-essential libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN python -m pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock

WORKDIR /opt
RUN git init /opt/resemble-enhance \
    && git -C /opt/resemble-enhance remote add origin https://github.com/resemble-ai/resemble-enhance.git \
    && git -C /opt/resemble-enhance fetch --depth=1 origin "${RESEMBLE_SOURCE_SHA}" \
    && git -C /opt/resemble-enhance checkout --detach FETCH_HEAD
WORKDIR /opt/resemble-enhance
RUN python -m pip install --no-deps --no-build-isolation .

RUN python - <<'PY'
from hashlib import sha256
from pathlib import Path
from huggingface_hub import snapshot_download

model_dir = Path("/opt/models")
snapshot_download(
    repo_id="ResembleAI/resemble-enhance",
    revision="cd13fe403de7b3150495a79418edfb38eb9562a5",
    local_dir=model_dir,
    allow_patterns=[
        "enhancer_stage2/hparams.yaml",
        "enhancer_stage2/ds/G/latest",
        "enhancer_stage2/ds/G/default/mp_rank_00_model_states.pt",
    ],
)
weights = model_dir / "enhancer_stage2/ds/G/default/mp_rank_00_model_states.pt"
hasher = sha256()
with weights.open("rb") as stream:
    for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
        hasher.update(chunk)
digest = hasher.hexdigest()
expected = "f9d035f318de3e6d919bc70cf7ad7d32b4fe92ec5cbe0b30029a27f5db07d9d6"
if digest != expected:
    raise SystemExit(f"unexpected model SHA-256: {digest}")
(model_dir / "MODEL-SHA256.txt").write_text(f"{digest}  {weights.relative_to(model_dir)}\n")
PY

ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

RUN python - <<'PY'
import torch
import torchaudio
import deepspeed
import resemble_enhance.enhancer.inference
assert torch.__version__ == "2.2.2+cpu", torch.__version__
assert torchaudio.__version__ == "2.2.2+cpu", torchaudio.__version__
assert not torch.cuda.is_available()
print(f"torch={torch.__version__} cuda_available={torch.cuda.is_available()}")
PY

ENTRYPOINT ["resemble-enhance"]
CMD ["--help"]
