import io
import json
from typing import List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .presidio import analyze_text, anonymize_text, find_custom_terms, supported_entities
from .extract import extract_text
from .redact import build_redaction_pairs, redact_file

MAX_UPLOAD_BYTES = 50 * 1024 * 1024

app = FastAPI(title="Redactor API")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["Content-Type"])


class TextRequest(BaseModel):
    text: str
    allow_list: Optional[List[str]] = []
    custom_terms: Optional[List[str]] = []


def _to_dicts(results):
    out = []
    for r in results:
        recognizer = "Custom Term" if r.entity_type == "CUSTOM_TERM" else (r.recognition_metadata or {}).get("recognizer_name", "Unknown")
        out.append({"entity_type": r.entity_type, "start": r.start, "end": r.end, "score": round(r.score, 2), "recognizer": recognizer})
    return out


async def _read_upload(file: UploadFile) -> bytes:
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(400, f"file too large (max {MAX_UPLOAD_BYTES // (1024*1024)} MB)")
    return data


def _parse_list(raw: Optional[str], name: str) -> List[str]:
    if not raw:
        return []
    try:
        v = json.loads(raw)
        if not isinstance(v, list):
            raise ValueError
        return [str(x) for x in v]
    except (ValueError, TypeError):
        raise HTTPException(400, f"{name} must be a JSON array")


def _run_analysis(text: str, al: List[str], ct: List[str]):
    results = analyze_text(text, allow_list=al)
    results += find_custom_terms(text, ct)
    return results


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
    results = _run_analysis(req.text, req.allow_list, req.custom_terms)
    return {"text": req.text, "results": _to_dicts(results)}


@app.post("/analyze-file")
async def analyze_file(file: UploadFile = File(...), allow_list: Optional[str] = Form(None), custom_terms: Optional[str] = Form(None)):
    data = await _read_upload(file)
    try:
        text = extract_text(file.filename, data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    results = _run_analysis(text, _parse_list(allow_list, "allow_list"), _parse_list(custom_terms, "custom_terms"))
    return {"text": text, "results": _to_dicts(results)}


@app.post("/anonymize")
def anonymize(req: TextRequest):
    if not req.text.strip():
        raise HTTPException(400, "text is empty")
    results = _run_analysis(req.text, req.allow_list, req.custom_terms)
    return {"text": anonymize_text(req.text, results).text, "results": _to_dicts(results)}


@app.post("/redact-file")
async def redact_file_endpoint(file: UploadFile = File(...), allow_list: Optional[str] = Form(None), custom_terms: Optional[str] = Form(None)):
    data = await _read_upload(file)
    try:
        text = extract_text(file.filename, data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    results = _run_analysis(text, _parse_list(allow_list, "allow_list"), _parse_list(custom_terms, "custom_terms"))
    try:
        out, media_type = redact_file(file.filename, data, build_redaction_pairs(text, results))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return StreamingResponse(io.BytesIO(out), media_type=media_type, headers={"Content-Disposition": f'attachment; filename="redacted_{file.filename}"'})
