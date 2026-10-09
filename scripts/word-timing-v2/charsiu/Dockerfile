# Charsiu forced aligner (A-CHAR). Evaluation only: model licence unstated.
FROM python:3.10.14-slim-bookworm@sha256:2407c61b1a18067393fecd8a22cf6fceede893b6aaca817bf9fbfe65e33614a3
ENV PIP_NO_CACHE_DIR=1 PYTHONUNBUFFERED=1 HF_HOME=/cache/hf NLTK_DATA=/opt/nltk_data
RUN pip install --extra-index-url https://download.pytorch.org/whl/cpu \
      torch==2.0.1+cpu numpy==1.26.4 transformers==4.30.2 huggingface_hub==0.23.5 \
      librosa==0.10.1 soundfile==0.12.1 praatio==6.2.0 nltk==3.8.1 g2p_en==2.1.0 \
      inflect==7.2.1 distance==0.1.3 g2pM==0.1.2.5 scipy==1.11.4
# Charsiu code at a pinned commit (only src/ is used)
ARG CHARSIU_SHA=13a69f2a22ca0c0962b75cc693399b0ae23a12c9
RUN python -c "import urllib.request,tarfile,io;d=urllib.request.urlopen('https://codeload.github.com/lingjzhu/charsiu/tar.gz/$CHARSIU_SHA').read();tarfile.open(fileobj=io.BytesIO(d)).extractall('/opt')" \
 && mv /opt/charsiu-$CHARSIU_SHA /opt/charsiu
# g2p_en nltk data at build time
RUN python -m nltk.downloader -d /opt/nltk_data averaged_perceptron_tagger cmudict punkt \
 && python -c "from g2p_en import G2p; print(G2p()('hello world'))"
COPY align_charsiu.py /app/align_charsiu.py
ENTRYPOINT ["python", "/app/align_charsiu.py"]
