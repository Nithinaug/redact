# DocRedact

PII detection and redaction tool for documents and images. Uses Microsoft Presidio with StanfordAIMI NER model for high-accuracy entity detection.

Supports: PDF, DOCX, XLSX, CSV, TXT, JPG, PNG, TIFF, BMP

## Quick start (Docker)

```bash
docker compose up --build
```

App runs at `http://localhost:8000`. First build downloads the NER model (~500MB).

## Local development

### Backend

```bash
cd api
pip install -r requirements.txt
```

Tesseract OCR required for image support:
- Windows: `winget install UB-Mannheim.TesseractOCR`
- Linux: `apt-get install tesseract-ocr`
- Mac: `brew install tesseract`

Start the API:
```bash
cd ..
python -m api.main
```

### Frontend

```bash
cd client
npm install
npm run dev
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:4173` | Comma-separated allowed origins |
| `VITE_API_URL` | `http://localhost:8000` | API URL for the frontend |
