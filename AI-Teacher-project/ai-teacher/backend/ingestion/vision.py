"""
Computer Vision for learning-material ingestion (section 16 technology
list). Without this, the pipeline is text-only: a scanned textbook page,
a diagram with labeled parts, or a formula that only exists as an image
inside a PDF/DOCX/PPTX is completely invisible to the RAG index - the
"identifying relevant chapters, sections, concepts, definitions, examples"
requirement (section 3) silently fails on anything that isn't native text.

This module extracts embedded/rendered images from uploaded material and
runs OCR (Tesseract via pytesseract) over them, so text baked into images
gets pulled into the same chunking/retrieval pipeline as everything else.
Fully offline - no API key, no network after the OCR engine is installed.

Deliberately conservative about noise: OCR is only run where it's likely
to add information the native text extractor already missed (a PDF page
with little/no extracted text - i.e. probably scanned; or any image
embedded directly in a DOCX/PPTX, since python-docx/python-pptx never
extract text from images at all).
"""
import io
import logging

from PIL import Image

logger = logging.getLogger("ai_teacher.vision")

MIN_OCR_CHARS = 8  # discard OCR noise shorter than this (stray marks, etc.)


def ocr_image(image: Image.Image) -> str:
    """Runs OCR on a single image. Returns '' (never raises) on any
    failure - a missing/broken OCR engine should degrade the material to
    text-only, not break the whole upload."""
    try:
        import pytesseract
        text = pytesseract.image_to_string(image).strip()
        return text if len(text) >= MIN_OCR_CHARS else ""
    except Exception as e:
        logger.warning(
            "OCR unavailable (%s: %s) - install `pytesseract` (pip) and the "
            "Tesseract binary (`sudo apt install tesseract-ocr`) to extract "
            "text from images/diagrams/scanned pages. Continuing with "
            "native text only.",
            type(e).__name__, e,
        )
        return ""


def ocr_pdf_scanned_pages(filepath: str, native_text_by_page: dict, resolution: int = 200) -> list:
    """Renders and OCRs only the pages pdfplumber found little/no native
    text on (heuristic for "this page is a scanned image, not real text"),
    and any page that contains embedded images worth checking. Returns a
    list of "[Page N - OCR] <text>" strings to fold into the document."""
    import pdfplumber

    results = []
    with pdfplumber.open(filepath) as pdf:
        for i, page in enumerate(pdf.pages):
            native_len = len(native_text_by_page.get(i, ""))
            has_images = len(page.images) > 0
            looks_scanned = native_len < 40
            if not (has_images or looks_scanned):
                continue
            try:
                rendered = page.to_image(resolution=resolution).original.convert("RGB")
            except Exception as e:
                logger.warning("Could not render page %d for OCR (%s: %s)", i + 1, type(e).__name__, e)
                continue
            text = ocr_image(rendered)
            if text:
                results.append(f"[Page {i+1} - OCR from image/diagram]\n{text}")
    return results


def extract_images_docx(filepath: str) -> list:
    """Pulls every embedded picture out of a .docx via its image relationships."""
    import docx
    doc = docx.Document(filepath)
    images = []
    for rel in doc.part.rels.values():
        if "image" in rel.reltype:
            try:
                images.append(Image.open(io.BytesIO(rel.target_part.blob)).convert("RGB"))
            except Exception:
                continue
    return images


def extract_images_pptx(filepath: str) -> list:
    """Pulls every picture shape out of a .pptx, slide by slide."""
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    prs = Presentation(filepath)
    images = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                try:
                    images.append(Image.open(io.BytesIO(shape.image.blob)).convert("RGB"))
                except Exception:
                    continue
    return images


def ocr_images(images: list) -> list:
    """OCRs a list of images, dropping any with no usable text."""
    texts = []
    for img in images:
        text = ocr_image(img)
        if text:
            texts.append(text)
    return texts
