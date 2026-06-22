import io

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .presidio import analyze_text, analyze_pages, anonymize_text, supported_entities
from .extract import extract_text, extract_pages, extension_of
from .redact import build_redaction_pairs, redact_file

MAX_UPLOAD_BYTES = 50 * 1024 * 1024

app = FastAPI(title="Redactor API")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["Content-Type"])


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
    ext = extension_of(file.filename)
    try:
        pages = extract_pages(data, ext)
    except ValueError as e:
        raise HTTPException(400, str(e))
    text = "\n".join(pages)
    results = analyze_pages(pages) if len(pages) > 1 else analyze_text(text)
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
    ext = extension_of(file.filename)
    try:
        pages = extract_pages(data, ext)
    except ValueError as e:
        raise HTTPException(400, str(e))
    text = "\n".join(pages)
    results = analyze_pages(pages) if len(pages) > 1 else analyze_text(text)
    try:
        out, media_type = redact_file(file.filename, data, build_redaction_pairs(text, results))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return StreamingResponse(io.BytesIO(out), media_type=media_type, headers={"Content-Disposition": f'attachment; filename="redacted_{file.filename}"'})
