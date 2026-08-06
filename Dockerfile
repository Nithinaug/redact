FROM node:20-slim AS frontend
WORKDIR /app/client
COPY client/package.json client/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY client/ ./
RUN npm run build

FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY api/requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt
RUN python -c "from presidio_analyzer.nlp_engine import TransformersNlpEngine; \
    e = TransformersNlpEngine(models=[{'lang_code': 'en', 'model_name': {'spacy': 'en_core_web_sm', 'transformers': 'StanfordAIMI/stanford-deidentifier-base'}}]); \
    e.load()"

COPY api/ ./api/
COPY --from=frontend /app/client/dist ./static

ENV CORS_ORIGINS=*
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "300"]
