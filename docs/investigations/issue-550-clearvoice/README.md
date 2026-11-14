# ClearerVoice CPU build

This isolated Docker context checks whether ClearerVoice MossFormer2 SE 48 kHz can run on CPU Linux. Its smoke test uses a generated one-second tone/noise fixture. The separate batch script processes explicitly mounted local audio offline.

## Pinned inputs

- Source: [ClearerVoice-Studio](https://github.com/modelscope/ClearerVoice-Studio/tree/6b3774dc79c46ae8bed2a4fa5f706f0ac8c75c61), commit `6b3774dc79c46ae8bed2a4fa5f706f0ac8c75c61` (Apache-2.0).
- Weights: [MossFormer2_SE_48K](https://huggingface.co/alibabasglab/MossFormer2_SE_48K/tree/eff8c97925c8bec812af707814b3e5d777fd4503), revision `eff8c97925c8bec812af707814b3e5d777fd4503` (Apache-2.0, 222 MB).
- Runtime: Python 3.11, PyTorch `2.5.1+cpu`, torchaudio `2.5.1+cpu`, torchvision `0.20.1+cpu`; Python dependencies are version-pinned in `requirements.cpu.txt`.

The model checkpoint is downloaded at image build time into ClearerVoice's configured `checkpoints/MossFormer2_SE_48K` directory. The smoke run sets Hugging Face offline mode and uses Docker `--network=none`, so it cannot fetch model files at inference time.

The source's editable install currently fails because its pinned `pyproject.toml` uses a legacy string for `project.license`. The image runs the pinned checkout directly through `PYTHONPATH` and installs its declared runtime dependencies without changing upstream source.

## Build and offline smoke run

Run from this directory:

```sh
docker build --file Dockerfile.cpu --tag issue550-clearvoice-cpu:pinned .

docker run --rm --network=none issue550-clearvoice-cpu:pinned
```

Keep private audio out of the build context. The built image reports 1,276,629,232 bytes via `docker image inspect`; Docker's image listing reports a different virtual size. The checkpoint SHA-256 is `03692b9f773bbd6bb43b9c5a41f96b1e28affd66e13796b7bec66ad3d8b227c6`.

`requirements.cpu.txt` pins the direct dependencies from the upstream package metadata. Transitive packages and the base image tag are not locked, so the build cannot yet be reproduced exactly.
