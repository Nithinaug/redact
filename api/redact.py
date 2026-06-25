import csv
import io

import fitz
import openpyxl
from docx import Document
from PIL import Image

from .extract import extension_of, IMAGE_EXTS
from .presidio import get_image_redactor

TYPES = {
    ".txt": "text/plain; charset=utf-8",
    ".json": "application/json",
    ".csv": "text/csv; charset=utf-8",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
    ".bmp": "image/bmp",
}


def build_redaction_pairs_from_dicts(text, results, split_tokens=False):
    pairs, seen = [], set()
    for r in sorted(results, key=lambda r: (r["end"] - r["start"], r.get("score", 0)), reverse=True):
        start, end = r["start"], r["end"]
        if start < 0 or end > len(text) or start >= end:
            continue
        original = text[start:end]
        if not original.strip() or len(original.strip()) < 3 or original in seen:
            continue
        seen.add(original)
        replacement = f"<{r['entity_type']}>"
        pairs.append((original, replacement))
        if split_tokens:
            for token in original.split():
                if token not in seen and token.strip():
                    seen.add(token)
                    pairs.append((token, replacement))
    pairs.sort(key=lambda p: len(p[0]), reverse=True)
    return pairs


def _apply_replacements(s, pairs):
    for original, replacement in pairs:
        s = s.replace(original, replacement)
    return s


def redact_file(filename, data, pairs):
    ext = extension_of(filename)
    if ext in (".txt", ".json"):
        out = _apply_replacements(data.decode("utf-8", errors="replace"), pairs).encode("utf-8")
    elif ext == ".csv":
        out = _redact_csv(data, pairs)
    elif ext == ".docx":
        out = _redact_docx(data, pairs)
    elif ext == ".xlsx":
        out = _redact_xlsx(data, pairs)
    elif ext == ".pdf":
        out = _redact_pdf(data, pairs)
    else:
        raise ValueError(f"unsupported file type: {ext}")
    return out, TYPES[ext]


def redact_image_file(data, entities):
    img = Image.open(io.BytesIO(data))
    fmt = img.format or "PNG"
    engine = get_image_redactor()
    redacted = engine.redact(img, fill=(0, 0, 0), entities=entities)
    buf = io.BytesIO()
    redacted.save(buf, format=fmt)
    ext = f".{fmt.lower()}"
    if ext == ".jpeg":
        ext = ".jpg"
    return buf.getvalue(), TYPES.get(ext, f"image/{fmt.lower()}")


def _redact_csv(data, pairs):
    rows = list(csv.reader(io.StringIO(data.decode("utf-8", errors="replace"))))
    for row in rows:
        for i, field in enumerate(row):
            row[i] = _apply_replacements(field, pairs)
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    return buf.getvalue().encode("utf-8")


def _redact_docx(data, pairs):
    doc = Document(io.BytesIO(data))
    for p in doc.paragraphs:
        for run in p.runs:
            new = _apply_replacements(run.text, pairs)
            if new != run.text:
                run.text = new
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    for run in p.runs:
                        new = _apply_replacements(run.text, pairs)
                        if new != run.text:
                            run.text = new
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def _redact_xlsx(data, pairs):
    wb = openpyxl.load_workbook(io.BytesIO(data))
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str):
                    new = _apply_replacements(cell.value, pairs)
                    if new != cell.value:
                        cell.value = new
    out = io.BytesIO()
    wb.save(out)
    wb.close()
    return out.getvalue()


def _redact_pdf(data, pairs):
    originals = list(set(p[0] for p in pairs))
    with fitz.open(stream=data, filetype="pdf") as doc:
        page_texts = {i: doc[i].get_text() for i in range(len(doc))}
        page_matches = {}
        for original in originals:
            for page_num, pt in page_texts.items():
                if original in pt:
                    page_matches.setdefault(page_num, set()).add(original)
        for page_num, matches in page_matches.items():
            page = doc[page_num]
            for original in matches:
                for rect in page.search_for(original):
                    page.add_redact_annot(rect, text="", fill=(0, 0, 0))
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
        out = io.BytesIO()
        doc.save(out, garbage=4, deflate=True, clean=True)
    return out.getvalue()
