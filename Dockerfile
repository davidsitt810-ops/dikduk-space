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
# everything in the Space: app.py, vowels.py, nikud.py, the classifiers and heads, lyrics_tehillim.json, static/ (the
# lab page; static/tehillim/ optionally holds Rabbi Alouf's mp3s), and ft/ when the GPU-tuned encoder exists
COPY . .
RUN mkdir -p /tmp/dkcache && chown -R user /app /tmp/dkcache
USER user
EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
