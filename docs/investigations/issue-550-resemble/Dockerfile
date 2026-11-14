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

COPY download_model.py smoke.py /tmp/
RUN python /tmp/download_model.py

ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

RUN python /tmp/smoke.py

ENTRYPOINT ["resemble-enhance"]
CMD ["--help"]
