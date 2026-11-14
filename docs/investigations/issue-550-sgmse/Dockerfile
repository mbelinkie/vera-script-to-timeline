# Linux x86_64 CPU-only runtime, pinned to the official Python 3.11.18 Bookworm
# multi-platform image manifest. Build with --platform linux/amd64.
FROM --platform=linux/amd64 python:3.11.18-slim-bookworm@sha256:94a8fee35252d06ab75856f15f12c7bae67b10e8a6da93c7fded82b2610926cd

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=6 \
    MKL_NUM_THREADS=6 \
    OPENBLAS_NUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1 \
    HOME=/tmp

# PESQ's only PyPI artifact is an sdist. The C toolchain is snapshot-pinned;
# pip's isolated Python build backend remains unpinned (see the README).
RUN rm -f /etc/apt/sources.list /etc/apt/sources.list.d/debian.sources \
    && printf '%s\n' \
        'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/20261112T000000Z bookworm main' \
        'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian-security/20261112T000000Z bookworm-security main' \
        > /etc/apt/sources.list \
    && apt-get -o Acquire::Check-Valid-Until=false update \
    && apt-get install -y --no-install-recommends build-essential ca-certificates git libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/sgmse
RUN git init \
    && git remote add origin https://github.com/sp-uhh/sgmse.git \
    && git fetch --depth=1 origin 1961cf4483e37df1bb92ccf0eb8b28bf6f44cb0e \
    && git checkout --detach FETCH_HEAD \
    && test "$(git rev-parse HEAD)" = 1961cf4483e37df1bb92ccf0eb8b28bf6f44cb0e

COPY requirements.lock /tmp/requirements.lock
RUN python -m pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock

COPY no-grad.py /opt/sgmse/no-grad.py
ENTRYPOINT ["python", "/opt/sgmse/no-grad.py"]
