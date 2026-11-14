# SGMSE+ EARS-Reverb CPU candidate

This is a staged, isolated Linux x86_64 CPU evaluation recipe for issue #550.
It has not been built or run yet. Do not use it for commercial work until the
checkpoint's training-data rights are clarified.

## Pins

- Source: official `sp-uhh/sgmse` at commit
  `1961cf4483e37df1bb92ccf0eb8b28bf6f44cb0e`.
- Checkpoint: first-party Hugging Face repo revision
  `89193ea626c85f3ba36c5ca6d604068ebb2e5e58`, file
  `pretrained_checkpoints/48_khz_models/ears_reverb.ckpt`.
- Checkpoint payload SHA-256:
  `9be62a3df0401398e5626a1c4dc65039220499d506941ecf110b52cccb7309b2`.
- Checkpoint size: 1,295,848,436 bytes.
- Base image: official `python:3.11.18-slim-bookworm` manifest digest
  `sha256:94a8fee35252d06ab75856f15f12c7bae67b10e8a6da93c7fded82b2610926cd`.

The [official source commit](https://github.com/sp-uhh/sgmse/tree/1961cf4483e37df1bb92ccf0eb8b28bf6f44cb0e),
[pinned checkpoint file](https://huggingface.co/sp-uhh/speech-enhancement-sgmse/blob/89193ea626c85f3ba36c5ca6d604068ebb2e5e58/pretrained_checkpoints/48_khz_models/ears_reverb.ckpt),
and [checkpoint upload commit](https://huggingface.co/sp-uhh/speech-enhancement-sgmse/commit/059b5ca85857dd73e4f3e84bb6889e6e47dcbf4d)
are first-party artifacts. The [EARS dataset README](https://github.com/facebookresearch/ears_dataset/blob/main/README.md)
and [EARS benchmark README](https://github.com/sp-uhh/ears_benchmark) declare CC BY-NC 4.0.
The [Python base image digest](https://hub.docker.com/layers/library/python/3.11.18-slim-bookworm/images/sha256-e9c1adfb591d78341433abc2eb24da1538271b2f31db198a3269c14c5143a00e)
is the official multi-platform image index for the tag above.

The code repository's pinned `requirements_version.txt` supplies the direct
runtime versions in `requirements.in`. The PyTorch `+cpu` suffix deliberately
selects CPU wheels. `requirements.lock` is the generated, hash-checked Linux
lock consumed by the Dockerfile.

Build limitation: `pesq==0.0.4` is published as a source distribution. pip's
default isolated build may resolve setuptools and wheel versions outside the
lock. The build pins the Debian compiler through a dated snapshot, but the
Python build backend is not fully locked; record the resulting environment if
reproducing this image. A follow-up can pin build-backend dependencies and
disable isolation if repeatable binary builds become necessary.

## License screen

The SGMSE code repository is MIT, and the Hugging Face model repository is
tagged MIT. The checkpoint is trained on EARS-Reverb. The official EARS dataset
repository and official EARS benchmark repository declare CC BY-NC 4.0 for
their code/data. EARS-Reverb is derived from EARS speech and multiple public
room impulse response datasets, each of which may carry separate terms.
The model-card MIT tag does not resolve whether those restrictions apply to
the learned checkpoint. This recipe is staged for local non-commercial
evaluation only; do not redistribute the checkpoint or use it commercially
without clarification from the rights holders.

## Stage, build, run

The checkpoint is downloaded on the host and verified before Docker runs:

```sh
cd out/issue550-sgmse
sh download-checkpoint.sh models
docker build --platform linux/amd64 -t vera-sgmse-cpu:issue550 .
```

Pass a folder containing a short, already-selected WAV excerpt as input. Keep
that folder read-only and choose an output folder under the task's local
workspace. Inference has no network, a read-only container root, 6 CPU cores,
and a 7 GiB memory cap:

```sh
sh run-inference.sh vera-sgmse-cpu:issue550 "$PWD/models" \
  /absolute/path/to/short-excerpt-folder \
  /absolute/path/to/issue550-sgmse-output
```

The runner uses the upstream enhancement script with `--device cpu` and its
default EARS-Reverb sampler settings (`--N 30`, PC sampler, ALD corrector, SNR
0.5). It preserves file names and writes results only to the output mount.

The Docker build needs network to fetch the pinned source and dependencies.
The inference container is explicitly run with `--network none`; its input
and checkpoint mounts are read-only. The build context contains only this
small recipe, never private audio.
