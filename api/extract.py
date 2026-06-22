import csv
import io
import os

import fitz
import openpyxl
from docx import Document

SUPPORTED_EXTENSIONS = {".txt", ".json", ".csv", ".pdf", ".docx", ".xlsx"}


def extension_of(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()


def extract_text(filename: str, data: bytes) -> str:
    ext = extension_of(filename)
    if ext in (".txt", ".json"):
        return data.decode("utf-8", errors="replace")
    if ext == ".csv":
        return _extract_csv(data)
    if ext == ".pdf":
        return _extract_pdf(data)
    if ext == ".docx":
        return _extract_docx(data)
    if ext == ".xlsx":
        return _extract_xlsx(data)
    raise ValueError(f"unsupported file type: {ext}")


def _extract_csv(data: bytes) -> str:
    text = data.decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(text))
    return "\n".join(" ".join(row) for row in reader)


def _extract_pdf(data: bytes) -> str:
    pages = extract_pages(data, ".pdf")
    text = "\n".join(pages)
    if not text.strip():
        raise ValueError("no text layer found - this PDF may be scanned (OCR not supported yet)")
    return text


def _extract_docx(data: bytes) -> str:
    doc = Document(io.BytesIO(data))
    lines = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            lines.append(" ".join(cell.text for cell in row.cells))
    return "\n".join(lines)


def extract_pages(data: bytes, ext: str) -> list:
    if ext == ".pdf":
        pages = []
        with fitz.open(stream=data, filetype="pdf") as doc:
            for page in doc:
                pages.append(page.get_text())
        return pages
    return [extract_text_from_ext(ext, data)]


def extract_text_from_ext(ext: str, data: bytes) -> str:
    if ext in (".txt", ".json"):
        return data.decode("utf-8", errors="replace")
    if ext == ".csv":
        return _extract_csv(data)
    if ext == ".docx":
        return _extract_docx(data)
    if ext == ".xlsx":
        return _extract_xlsx(data)
    raise ValueError(f"unsupported file type: {ext}")


def _extract_xlsx(data: bytes) -> str:
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    lines = []
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            cells = [str(c) for c in row if c is not None]
            if cells:
                lines.append(" ".join(cells))
    wb.close()
    return "\n".join(lines)
