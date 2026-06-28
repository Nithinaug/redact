# DocRedact

A web application that detects and redacts personally identifiable information (PII) from documents and images. A FastAPI backend runs uploaded files through a three-layer detection pipeline — a Stanford NER transformer model, Presidio's built-in pattern recognizers, and custom regex recognizers — then presents the results in a React frontend where users can review, toggle entity types, and download redacted files.

## Overview

Staff upload a document or paste text, and the system extracts text content, runs PII analysis, and displays the results with highlighted entities in a document-style preview. Users review the detections, toggle entity types on or off (human-in-the-loop), and download the redacted file. PDFs are redacted with black bars over the original layout, DOCX/XLSX/CSV files get text replacement, and images are redacted using Presidio's ImageRedactorEngine with Tesseract OCR.

## Features

* **Three-layer PII detection**: StanfordAIMI/stanford-deidentifier-base NER model + Presidio regex recognizers + custom pattern recognizers that detect entity types beyond standard categories (Singapore UEN, financial identifiers), with a tuned confidence threshold (0.5) to minimize false positives.
* **Post-processing pipeline**: reclassification (e.g. "Washington DC" from PERSON to LOCATION), deduplication of overlapping detections, and merging of adjacent entities.
* **Human-in-the-loop review**: entity type toggles with counts let users control exactly what gets redacted before downloading.
* **Multi-format support**: PDF, DOCX, XLSX, CSV, TXT, JSON, JPG, PNG, TIFF, BMP.
* **PDF black-bar redaction**: uses PyMuPDF to draw pixel-level redaction annotations over the original document layout, preserving formatting with entity type labels.
* **Office document redaction**: structure-aware run-level replacements inside DOCX and cell-level replacements in XLSX, preserving document structure.
* **Image redaction**: Tesseract OCR with grayscale-to-binary preprocessing extracts text for analysis, Presidio ImageRedactorEngine handles pixel-level redaction.
* **Text mode**: paste text directly, analyze, review highlights, and redact in-browser without file upload.
* **Pre-computed results**: the redact endpoint accepts already-analyzed results to avoid re-analysis on download.

## Architecture

The FastAPI backend loads the Stanford NER model and Presidio engines once at startup (cached via `lru_cache`). On file upload, text is extracted by format-specific extractors (PyMuPDF for PDF, python-docx for DOCX, openpyxl for XLSX, pytesseract for images), then run through the analysis pipeline. Results are returned to the frontend as character-offset spans. When the user requests redaction, the filtered results are sent back and the appropriate redactor (PDF black bars, text replacement, or image redaction) produces the output file.

## Tech stack

* **Backend**: Python, FastAPI, Uvicorn, Microsoft Presidio, StanfordAIMI/stanford-deidentifier-base, PyMuPDF, pytesseract, Pillow
* **Frontend**: React, Vite

## Project structure

* `api/` — FastAPI service: text extraction, PII analysis, redaction, custom recognizers
* `client/` — React application (Vite)
* `Dockerfile`, `docker-compose.yml` — single-container deployment

## Prerequisites

* Python 3.11+
* Node.js 20+
* Tesseract OCR (for image support)
* Docker (for containerized deployment)

## Local development

Start the backend:

```
cd api
pip install -r requirements.txt
cd ..
python -m api.main
```

Tesseract OCR is required for image redaction:

* Windows: `winget install UB-Mannheim.TesseractOCR`
* Linux: `apt-get install tesseract-ocr`
* Mac: `brew install tesseract`

Start the frontend in a separate terminal:

```
cd client
npm install
npm run dev
```

The Vite dev server runs on http://localhost:5173 and connects to the API at http://localhost:8000.

## Docker

The entire application (API and the built frontend) runs as a single container:

```
docker compose up --build
```

Open http://localhost:8000. The first build downloads the Stanford NER model (~500MB) and bakes it into the image.

## API

* `GET /health` — service health check
* `GET /entities` — list supported entity types
* `POST /analyze` — analyze plain text, returns entity spans
* `POST /analyze-file` — upload and analyze a file, returns extracted text and entity spans
* `POST /anonymize` — analyze and anonymize text in one step
* `POST /redact-file` — upload a file with optional pre-computed results, returns the redacted file
