import io
import json
import os
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from .presidio import analyze_text, anonymize_text, supported_entities
from .extract import extract_text, extension_of
from .redact import build_redaction_pairs_from_dicts, redact_file

MAX_UPLOAD_BYTES = 25 * 1024 * 1024

app = FastAPI(title="Redactor API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


class TextRequest(BaseModel):
    text: str


def _to_dicts(results):
    return [{"entity_type": r.entity_type, "start": r.start, "end": r.end, "score": round(r.score, 2)} for r in results]


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
    return {"text": req.text, "results": _to_dicts(analyze_text(req.text))}


@app.post("/analyze-file")
async def analyze_file(file: UploadFile = File(...)):
    data = await _read_upload(file)
    try:
        text = extract_text(file.filename, data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"text": text, "results": _to_dicts(analyze_text(text))}


@app.post("/anonymize")
def anonymize(req: TextRequest):
    if not req.text.strip():
        raise HTTPException(400, "text is empty")
    results = analyze_text(req.text)
    return {"text": anonymize_text(req.text, results).text, "results": _to_dicts(results)}


@app.post("/redact-file")
async def redact_file_endpoint(request: Request, file: UploadFile = File(...), results: Optional[str] = Form(None)):
    data = await _read_upload(file)
    try:
        text = extract_text(file.filename, data)
    except ValueError as e:
        raise HTTPException(400, str(e))

    if results:
        try:
            result_dicts = json.loads(results)
        except (ValueError, TypeError):
            raise HTTPException(400, "results must be a JSON array")
    else:
        result_dicts = _to_dicts(analyze_text(text))

    if await request.is_disconnected():
        return Response(status_code=499)

    try:
        pairs = build_redaction_pairs_from_dicts(text, result_dicts, split_tokens=extension_of(file.filename) == ".csv")
        out, media_type = redact_file(file.filename, data, pairs)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return StreamingResponse(io.BytesIO(out), media_type=media_type, headers={"Content-Disposition": f'attachment; filename="redacted_{file.filename}"'})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True, timeout_keep_alive=300)
