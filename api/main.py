import io

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .engine import analyze_text, anonymize_text, supported_entities
from .extract import extract_text
from .redact import build_redaction_pairs, redact_file

MAX_UPLOAD_BYTES = 50 * 1024 * 1024

app = FastAPI(title="Redactor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


class TextRequest(BaseModel):
    text: str


def _results_to_dicts(results):
    return [
        {"entity_type": r.entity_type, "start": r.start, "end": r.end, "score": r.score}
        for r in results
    ]


async def _read_upload(file: UploadFile) -> bytes:
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail=f"file too large (max {MAX_UPLOAD_BYTES // (1024*1024)} MB)")
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
        raise HTTPException(status_code=400, detail="text is empty")
    results = analyze_text(req.text)
    return {"text": req.text, "results": _results_to_dicts(results)}


@app.post("/analyze-file")
async def analyze_file(file: UploadFile = File(...)):
    data = await _read_upload(file)
    try:
        text = extract_text(file.filename, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    results = analyze_text(text)
    return {"text": text, "results": _results_to_dicts(results)}


@app.post("/anonymize")
def anonymize(req: TextRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text is empty")
    results = analyze_text(req.text)
    out = anonymize_text(req.text, results)
    return {"text": out.text, "results": _results_to_dicts(results)}


@app.post("/redact-file")
async def redact_file_endpoint(file: UploadFile = File(...)):
    data = await _read_upload(file)
    try:
        text = extract_text(file.filename, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    results = analyze_text(text)
    pairs = build_redaction_pairs(text, results)
    try:
        out, media_type = redact_file(file.filename, data, pairs)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    out_name = "redacted_" + file.filename
    return StreamingResponse(
        io.BytesIO(out),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{out_name}"'},
    )
