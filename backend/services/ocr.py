"""Recognize only a selected image area using PyMuPDF's bundled OCR engine."""

import math
import threading

import fitz

from backend.core.paths import resource_root
from backend.services.pdf_reader import PdfValidationError


_OCR_LOCK = threading.Lock()
MAX_OCR_PIXELS = 4_000_000


def recognize_area(page, area, protected=()):
    tessdata = resource_root() / "models" / "tessdata"
    if not (tessdata / "eng.traineddata").is_file():
        raise PdfValidationError(
            "This PDF contains image text, but the offline OCR data is missing. "
            "For the website server, run python scripts/prepare_ocr_data.py once. "
            "For the desktop app, install the updated BharatDocs app with OCR included."
        )
    scale = min(300 / 72, math.sqrt(MAX_OCR_PIXELS / area.get_area()))
    with _OCR_LOCK:
        try:
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=area, colorspace=fitz.csRGB, alpha=False)
            origin_x, origin_y = pix.x, pix.y
            # White margins let Tesseract recognize even one tightly selected line.
            padding = max(10, round(6 * scale))
            padded = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, pix.width + 2 * padding, pix.height + 2 * padding), False)
            padded.clear_with(255)
            pix.set_origin(padding, padding)
            padded.copy(pix, pix.irect)
            dpi = max(1, round(scale * 72))
            padded.set_dpi(dpi, dpi)
            with fitz.open("pdf", padded.pdfocr_tobytes(language="eng", tessdata=str(tessdata))) as recognized:
                words = recognized[0].get_text("words", sort=True)
                # OCR PDF coordinates use its rounded integer DPI; map back to the
                # rendered pixel origin, then to the original PDF coordinates.
                factor = dpi / 72
                lines = {}
                for x0, y0, x1, y1, text, block, line, _word in words:
                    # Table borders occasionally appear as isolated |, _, or ~.
                    if not any(character.isalnum() for character in text) and text not in ("&", "-", "/"):
                        continue
                    box = fitz.Rect((x0 * factor - padding + origin_x) / scale,
                                    (y0 * factor - padding + origin_y) / scale,
                                    (x1 * factor - padding + origin_x) / scale,
                                    (y1 * factor - padding + origin_y) / scale) & area
                    if box.is_empty or any(box.intersects(mask) for mask in protected):
                        continue
                    lines.setdefault((block, line), []).append((text, list(box)))
                lines = [words for words in lines.values()
                         if any(any(character.isalnum() for character in text) for text, _box in words)]
                return (" ".join(" ".join(text for text, _box in words) for words in lines),
                        [box for words in lines for _text, box in words])
        except (RuntimeError, ValueError, fitz.FileDataError) as error:
            raise PdfValidationError(
                f"The image text on page {page.number + 1} could not be read by offline OCR. "
                "Try a clearer PDF scan."
            ) from error
