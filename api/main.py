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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


class TextRequest(BaseModel):
    text: str
    allow_list: Optional[List[str]] = []
    custom_terms: Optional[List[str]] = []


def _results_to_dicts(results, text: str = ""):
    out = []
    for r in results:
        recognizer = "Custom Term"
        if r.entity_type != "CUSTOM_TERM" and r.recognition_metadata:
            recognizer = r.recognition_metadata.get("recognizer_name", "Unknown")
        out.append({
            "entity_type": r.entity_type,
            "start": r.start,
            "end": r.end,
            "score": round(r.score, 2),
            "recognizer": recognizer,
        })
    return out


async def _read_upload(file: UploadFile) -> bytes:
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail=f"file too large (max {MAX_UPLOAD_BYTES // (1024*1024)} MB)")
    return data


def _parse_json_field(raw: Optional[str], field_name: str) -> List[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
        if not isinstance(value, list):
            raise ValueError
        return [str(v) for v in value]
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail=f"{field_name} must be a JSON array of strings")


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
    results = analyze_text(req.text, allow_list=req.allow_list)
    results += find_custom_terms(req.text, req.custom_terms)
    return {"text": req.text, "results": _results_to_dicts(results, req.text)}


@app.post("/analyze-file")
async def analyze_file(
    file: UploadFile = File(...),
    allow_list: Optional[str] = Form(None),
    custom_terms: Optional[str] = Form(None),
):
    data = await _read_upload(file)
    try:
        text = extract_text(file.filename, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    al = _parse_json_field(allow_list, "allow_list")
    ct = _parse_json_field(custom_terms, "custom_terms")
    results = analyze_text(text, allow_list=al)
    results += find_custom_terms(text, ct)
    return {"text": text, "results": _results_to_dicts(results, text)}


@app.post("/anonymize")
def anonymize(req: TextRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text is empty")
    results = analyze_text(req.text, allow_list=req.allow_list)
    results += find_custom_terms(req.text, req.custom_terms)
    out = anonymize_text(req.text, results)
    return {"text": out.text, "results": _results_to_dicts(results, req.text)}


@app.post("/redact-file")
async def redact_file_endpoint(
    file: UploadFile = File(...),
    allow_list: Optional[str] = Form(None),
    custom_terms: Optional[str] = Form(None),
):
    data = await _read_upload(file)
    try:
        text = extract_text(file.filename, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    al = _parse_json_field(allow_list, "allow_list")
    ct = _parse_json_field(custom_terms, "custom_terms")
    results = analyze_text(text, allow_list=al)
    results += find_custom_terms(text, ct)
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
