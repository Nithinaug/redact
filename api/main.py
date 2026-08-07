import asyncio
import io
import json
import os
import zipfile
from typing import Optional

from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from .presidio import analyze_text, anonymize_text, supported_entities
from .extract import extract_text, extension_of, IMAGE_EXTS
from .redact import redact_file, redact_image_file

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_ZIP_ENTRIES = 50

app = FastAPI(title="Redactor API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:4173").split(","),
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
        text = await run_in_threadpool(extract_text, file.filename, data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    results = await run_in_threadpool(analyze_text, text)
    return {"text": text, "results": _to_dicts(results)}


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
        text = await run_in_threadpool(extract_text, file.filename, data)
    except ValueError as e:
        raise HTTPException(400, str(e))

    if results:
        try:
            result_dicts = json.loads(results)
        except (ValueError, TypeError):
            raise HTTPException(400, "results must be a JSON array")
    else:
        result_dicts = _to_dicts(await run_in_threadpool(analyze_text, text))

    if await request.is_disconnected():
        return Response(status_code=499)

    try:
        out, media_type = await _redact_one(file.filename, data, text, result_dicts)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return StreamingResponse(io.BytesIO(out), media_type=media_type, headers={"Content-Disposition": f'attachment; filename="redacted_{file.filename}"'})


async def _redact_one(filename, data, text, result_dicts):
    ext = extension_of(filename)
    if ext in IMAGE_EXTS:
        entities = list(set(r["entity_type"] for r in result_dicts))
        return await run_in_threadpool(redact_image_file, data, entities)
    return await run_in_threadpool(redact_file, filename, data, text, result_dicts)


def _open_zip(data: bytes):
    try:
        in_zip = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise ValueError("not a valid zip file")
    entries = [n for n in in_zip.namelist() if not n.endswith("/") and not n.startswith("__MACOSX")]
    if not entries:
        raise ValueError("zip file is empty")
    if len(entries) > MAX_ZIP_ENTRIES:
        raise ValueError(f"too many files in zip (max {MAX_ZIP_ENTRIES})")
    return in_zip, entries


async def _analyze_zip_entry(name, data):
    try:
        text = await run_in_threadpool(extract_text, name, data)
        results = _to_dicts(await run_in_threadpool(analyze_text, text))
        return name, text, results, None
    except HTTPException as e:
        return name, None, None, e.detail
    except Exception as e:
        return name, None, None, str(e)


@app.post("/analyze-zip")
async def analyze_zip_endpoint(file: UploadFile = File(...)):
    data = await _read_upload(file)
    try:
        in_zip, entries = _open_zip(data)
    except ValueError as e:
        raise HTTPException(400, str(e))

    outcomes = await asyncio.gather(*(_analyze_zip_entry(name, in_zip.read(name)) for name in entries))
    files, errors = [], []
    for name, text, results, err in outcomes:
        if err:
            errors.append({"name": name, "error": err})
        else:
            files.append({"name": name, "text": text, "results": results})
    return {"files": files, "errors": errors}


@app.post("/redact-zip")
async def redact_zip_endpoint(file: UploadFile = File(...), results: str = Form(...)):
    data = await _read_upload(file)
    try:
        in_zip, entries = _open_zip(data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    try:
        results_map = json.loads(results)
    except (ValueError, TypeError):
        raise HTTPException(400, "results must be a JSON object")

    async def handle(name):
        try:
            entry_data = in_zip.read(name)
            text = await run_in_threadpool(extract_text, name, entry_data)
            out, _ = await _redact_one(name, entry_data, text, results_map.get(name, []))
            return name, out, None
        except HTTPException as e:
            return name, None, e.detail
        except Exception as e:
            return name, None, str(e)

    outcomes = await asyncio.gather(*(handle(name) for name in entries))

    out_buf = io.BytesIO()
    errors = []
    with zipfile.ZipFile(out_buf, "w", zipfile.ZIP_DEFLATED) as out_zip:
        for name, out, err in outcomes:
            if err:
                errors.append(f"{name}: {err}")
                continue
            parts = name.rsplit("/", 1)
            redacted_name = f"{parts[0]}/redacted_{parts[1]}" if len(parts) == 2 else f"redacted_{name}"
            out_zip.writestr(redacted_name, out)
        if errors:
            out_zip.writestr("_errors.txt", "\n".join(errors))
    out_buf.seek(0)
    return StreamingResponse(out_buf, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="redacted_{file.filename}"'})


STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True, timeout_keep_alive=300)
