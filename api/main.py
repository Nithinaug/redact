import io
import os

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .presidio import analyze_text, anonymize_text, supported_entities
from .extract import extract_text
from .redact import build_redaction_pairs, redact_file

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

app = FastAPI(title="Redactor API")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["Content-Type"])


class TextRequest(BaseModel):
    text: str


def _to_dicts(results):
    out = []
    for r in results:
        out.append({"entity_type": r.entity_type, "start": r.start, "end": r.end, "score": round(r.score, 2), "recognizer": (r.recognition_metadata or {}).get("recognizer_name", "Unknown")})
    return out


async def _read_upload(file: UploadFile) -> bytes:
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(400, f"file too large (max {MAX_UPLOAD_BYTES // (1024*1024)} MB)")
    return data


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/entities")
def entities(language: str = "en"):
    return {"entities": supported_entities(language)}


@app.post("/analyze")
def analyze(req: TextRequest):
    if not req.text.strip():
        raise HTTPException(400, "text is empty")
    results = analyze_text(req.text)
    return {"text": req.text, "results": _to_dicts(results)}


@app.post("/analyze-file")
async def analyze_file(file: UploadFile = File(...)):
    data = await _read_upload(file)
    try:
        text = extract_text(file.filename, data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    results = analyze_text(text)
    return {"text": text, "results": _to_dicts(results)}


@app.post("/anonymize")
def anonymize(req: TextRequest):
    if not req.text.strip():
        raise HTTPException(400, "text is empty")
    results = analyze_text(req.text)
    return {"text": anonymize_text(req.text, results).text, "results": _to_dicts(results)}


@app.post("/redact-file")
async def redact_file_endpoint(file: UploadFile = File(...)):
    data = await _read_upload(file)
    try:
        text = extract_text(file.filename, data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    results = analyze_text(text)
    try:
        out, media_type = redact_file(file.filename, data, build_redaction_pairs(text, results))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return StreamingResponse(io.BytesIO(out), media_type=media_type, headers={"Content-Disposition": f'attachment; filename="redacted_{file.filename}"'})
