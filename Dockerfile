FROM python:3.11-slim
# ffmpeg decodes whatever the phone records (m4a, webm, wav)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1000 user
WORKDIR /app
RUN pip install --no-cache-dir torch==2.4.1 --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir transformers==4.44.2 huggingface_hub fastapi uvicorn numpy requests
ENV HF_HOME=/app/hf HF_HUB_DISABLE_TELEMETRY=1
# both models (about 1.3 GB each) are downloaded while the image builds, so a cold start only has to load them
RUN python -c "from transformers import Wav2Vec2ForCTC, Wav2Vec2FeatureExtractor, Wav2Vec2Processor; from huggingface_hub import hf_hub_download; \
m='facebook/wav2vec2-xlsr-53-espeak-cv-ft'; Wav2Vec2FeatureExtractor.from_pretrained(m); Wav2Vec2ForCTC.from_pretrained(m); hf_hub_download(m,'vocab.json'); \
a='jonatasgrosman/wav2vec2-large-xlsr-53-arabic'; Wav2Vec2Processor.from_pretrained(a); Wav2Vec2ForCTC.from_pretrained(a)"
# whatever is in the Space itself (at least this Dockerfile and README.md)
COPY . .
# The code, the trained heads (letter_head.pt, full_head.pt), the classifiers, lyrics_tehillim.json and static/ (the
# lab page, plus static/tehillim/ with Rabbi Alouf's mp3s) come from the public GitHub repo at build time, so the
# Space never needs the web uploader for binary files. The ADD line fetches the branch's commit feed first: a new
# commit on GitHub changes that file and invalidates the layers below on the next build ("Factory rebuild" on the
# Space forces a fresh fetch either way).
ADD https://github.com/davidsitt810-ops/dikduk-space/commits/main.atom /tmp/github_main.atom
RUN python -c "import urllib.request, tarfile, io, os, shutil; \
u = 'https://github.com/davidsitt810-ops/dikduk-space/archive/refs/heads/main.tar.gz'; \
t = tarfile.open(fileobj=io.BytesIO(urllib.request.urlopen(u, timeout=120).read())); t.extractall('/tmp/src'); \
r = os.path.join('/tmp/src', os.listdir('/tmp/src')[0]); skip = {'.git', '.github', 'Dockerfile', 'README.md', 'README_REPO.md', 'Dikduk.ipynb'}; \
[shutil.copytree(os.path.join(r, n), os.path.join('/app', n), dirs_exist_ok=True) if os.path.isdir(os.path.join(r, n)) else shutil.copy2(os.path.join(r, n), '/app') for n in os.listdir(r) if n not in skip]; \
shutil.rmtree('/tmp/src'); print('from github:', sorted(n for n in os.listdir('/app') if n != 'hf'), 'tehillim mp3s:', len(os.listdir('/app/static/tehillim')))"
RUN mkdir -p /tmp/dkcache && chown -R user /app /tmp/dkcache
USER user
EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
