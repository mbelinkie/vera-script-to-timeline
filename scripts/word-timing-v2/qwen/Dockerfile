# syntax=docker/dockerfile:1
FROM --platform=linux/amd64 python@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7
# python:3.12.11-slim-bookworm
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONUNBUFFERED=1 \
    HF_HOME=/cache/hf TOKENIZERS_PARALLELISM=false
WORKDIR /app
COPY requirements.lock /app/requirements.lock
RUN pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.lock
COPY align_qwen.py /app/align_qwen.py
ENTRYPOINT ["python", "/app/align_qwen.py"]
