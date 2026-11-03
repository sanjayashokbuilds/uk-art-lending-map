"""Turn a downloaded charge deed (PDF) into text.

Most deeds filed since 2013 are scans. pypdf handles the ones with a text
layer; for scans, pass --ocr and install Tesseract + Poppler
(on a Mac: brew install tesseract poppler; then pip install pytesseract pdf2image).
"""

from pathlib import Path

from pypdf import PdfReader

MIN_TEXT = 200  # fewer characters than this means "probably a scan"


def pdf_text(path, ocr=False, max_pages=40):
    """Extract text, caching it next to the PDF so reruns skip the slow OCR."""
    path = Path(path)
    cache = path.with_suffix(".txt")
    if cache.exists():
        text = cache.read_text()
        source = "ocr" if text.startswith("\x00ocr\n") else "text"
        return text.removeprefix("\x00ocr\n"), source if text.strip() else "none"
    text, source = _extract(path, ocr, max_pages)
    if source == "ocr" or len(text.strip()) >= MIN_TEXT:
        cache.write_text(("\x00ocr\n" if source == "ocr" else "") + text)
    return text, source


def _extract(path, ocr, max_pages):
    text = ""
    try:
        reader = PdfReader(str(path))
        pages = reader.pages[:max_pages]
        text = "\n".join((p.extract_text() or "") for p in pages)
    except Exception:
        text = ""
    if len(text.strip()) >= MIN_TEXT or not ocr:
        return text, "text" if text.strip() else "none"
    try:
        import pytesseract
        from pdf2image import convert_from_path
    except ImportError:
        raise SystemExit(
            "OCR needs: brew install tesseract poppler && "
            "pip install pytesseract pdf2image"
        )
    images = convert_from_path(str(path), dpi=200, last_page=max_pages)
    return "\n".join(pytesseract.image_to_string(im) for im in images), "ocr"
