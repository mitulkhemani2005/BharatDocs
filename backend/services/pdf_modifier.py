import html
import math
from pathlib import Path

import fitz

from backend.core.paths import resource_root


FONT_DIRECTORY = resource_root() / "fonts"
FONT_FILES = {
    "Noto Sans Devanagari": "NotoSansDevanagari-Regular.ttf",
}
DEFAULT_TEXT_OPTIONS = {
    "font_family": "Noto Sans Devanagari",
    "font_size": 14,
    "vertical_padding": 2,
    "minimum_scale": 0.7,
}


class PdfProcessingError(Exception):
    """Raised when translated text cannot be safely rendered into the PDF."""


def _render_options(options):
    options = {**DEFAULT_TEXT_OPTIONS, **(options or {})}
    font_family = options["font_family"]
    if not isinstance(font_family, str) or font_family not in FONT_FILES:
        raise PdfProcessingError("Noto Sans Devanagari is the supported Hindi print font.")
    try:
        font_size = float(options["font_size"])
        vertical_padding = float(options["vertical_padding"])
        minimum_scale = float(options["minimum_scale"])
    except (TypeError, ValueError) as error:
        raise PdfProcessingError("Hindi PDF text settings must be numeric.") from error

    if not 8 <= font_size <= 18:
        raise PdfProcessingError("Hindi PDF font size must be between 8 and 18 points.")
    if not 0 <= vertical_padding <= 3:
        raise PdfProcessingError("Hindi PDF vertical padding must be between 0 and 3 points.")
    if not 0.5 <= minimum_scale <= 1:
        raise PdfProcessingError("Hindi PDF minimum scale must be between 0.5 and 1.")
    return font_family, font_size, vertical_padding, minimum_scale


def _font_css(font_family, font_size):
    filename = FONT_FILES[font_family]
    return f"""
        @font-face {{
            font-family: 'PrintHindi';
            src: url('{filename}');
            font-weight: 400;
            font-style: normal;
        }}
        html, body, p {{
            font-family: 'PrintHindi';
            font-size: {font_size}pt;
            font-weight: 400;
            color: #111111;
            margin: 0;
            padding: 0;
        }}
        p {{
            text-align: left;
            font-weight: 400;
            line-height: 1.5;
            white-space: nowrap;
        }}
    """


def _expanded_text_rect(page, bbox, vertical_padding, vertical_offset=0):
    x0, y0, x1, y1 = bbox
    return fitz.Rect(
        x0,
        max(page.rect.y0, y0 - vertical_padding + vertical_offset),
        x1,
        min(page.rect.y1, y1 + vertical_padding + vertical_offset),
    )


def _prepare_hindi_text(document, text, font_size, css, archive):
    """Shape once, then measure painted ink including every upper/lower matra."""
    page = document.new_page(width=max(400, len(text) * font_size * 1.5), height=font_size * 5)
    remaining, _ = page.insert_htmlbox(
        page.rect, f'<p lang="hi">{html.escape(text, quote=False)}</p>',
        css=css, archive=archive, scale_low=1,
    )
    if remaining < 0:
        raise PdfProcessingError("Hindi text could not be shaped into a single line.")
    blocks = page.get_text("blocks")
    if not blocks:
        raise PdfProcessingError("Hindi text could not be measured.")
    bounds = fitz.Rect(blocks[0][:4])
    for block in blocks[1:]:
        bounds |= fitz.Rect(block[:4])
    # Use alpha coverage for measurement only. Output remains shaped vector text.
    resolution = 3
    pix = page.get_pixmap(matrix=fitz.Matrix(resolution, resolution), clip=(bounds + (-2, -2, 2, 2)) & page.rect, alpha=True)
    alpha = pix.samples[3::4]
    left, top, right, bottom = pix.width, pix.height, 0, 0
    for y in range(pix.height):
        row = alpha[y * pix.width:(y + 1) * pix.width]
        if row.strip(b"\x00"):
            left = min(left, len(row) - len(row.lstrip(b"\x00")))
            right = max(right, len(row.rstrip(b"\x00")))
            top = min(top, y)
            bottom = y + 1
    if right <= left or bottom <= top:
        raise PdfProcessingError("Hindi text did not contain visible glyphs.")
    ink = fitz.Rect((pix.x + left) / resolution, (pix.y + top) / resolution,
                    (pix.x + right) / resolution, (pix.y + bottom) / resolution)
    return page.number, (ink + (-0.25, -0.25, 0.25, 0.25)) & page.rect


def _fit_text_rect(destination, ink, minimum_scale):
    scale = min(1, destination.width / ink.width, destination.height / ink.height)
    if scale < minimum_scale:
        raise PdfProcessingError("Hindi text needs more space to keep its matras readable. Edit the configuration and enlarge the Hindi placement area.")
    width, height = ink.width * scale, ink.height * scale
    x = destination.x0 + (destination.width - width) / 2
    y = destination.y0 + (destination.height - height) / 2
    return fitz.Rect(x, y, x + width, y + height)


def _source_clear_rect(bbox, source_spans):
    clear = fitz.Rect(bbox)
    for span in source_spans:
        rect = fitz.Rect(span["bbox"])
        if ((rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2) in bbox:
            clear |= rect + (-0.25, -0.25, 0.25, 0.25)
    return clear


def _layout_moves(options):
    moves = []
    try:
        for move in (options or {}).get("move_regions", []):
            source, target = fitz.Rect(move["rect"]), fitz.Rect(move["destination"])
            if (source.is_empty or target.is_empty
                    or not all(math.isfinite(value) for value in (*source, *target))):
                raise ValueError("Invalid move")
            moves.append((source, target))
    except (KeyError, TypeError, ValueError) as error:
        raise PdfProcessingError("PDF move_regions must contain valid source/destination rectangles.") from error
    return moves


def apply_translations_to_pdf(
    input_pdf_path,
    output_pdf_path,
    translated_regions,
    text_options=None,
):
    font_family, font_size, vertical_padding, minimum_scale = _render_options(text_options)
    font_path = FONT_DIRECTORY / FONT_FILES[font_family]
    if not font_path.is_file():
        raise PdfProcessingError(f"The {font_family} font file is missing.")
    output_path = Path(output_pdf_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    archive = fitz.Archive(str(FONT_DIRECTORY))
    css = _font_css(font_family, font_size)
    moves = _layout_moves(text_options)

    try:
        with fitz.open(input_pdf_path) as doc, fitz.open(input_pdf_path) as original, fitz.open() as text_doc:
            for document in (doc, original):
                for page in document:
                    if page.rotation:
                        page.remove_rotation()
            prepared = {}
            if doc.needs_pass or doc.is_encrypted:
                raise PdfProcessingError("Password-protected PDFs cannot be translated.")

            page_regions = {}
            for region in translated_regions:
                page_index = region.get("page")
                if not isinstance(page_index, int) or not 0 <= page_index < doc.page_count:
                    continue
                hindi_text = region.get("hindi_text", "").strip()
                if not hindi_text:
                    continue
                bbox = fitz.Rect(region["rect"]) & doc[page_index].rect
                if bbox.is_empty or bbox.is_infinite:
                    continue
                page_regions.setdefault(page_index, []).append((
                    bbox,
                    hindi_text,
                    region.get("region_name", ""),
                    float(region.get("text_offset_y", 0)),
                    region.get("text_rect"),
                ))

            # Finish the source document before importing its PDF resources.
            for regions in page_regions.values():
                for _bbox, text, _name, _offset, _destination in regions:
                    if text not in prepared:
                        prepared[text] = _prepare_hindi_text(text_doc, text, font_size, css, archive)

            for page_index, regions in page_regions.items():
                page = doc[page_index]

                # Clear every target first so text from a neighboring region is never erased later.
                source_spans = [span for block in page.get_text("dict")["blocks"]
                                for line in block.get("lines", []) for span in line["spans"]]
                for source, target in moves:
                    if not page.rect.contains(source) or not page.rect.contains(target):
                        raise PdfProcessingError("A PDF move_regions rectangle is outside the page.")
                    page.draw_rect(source, fill=(1, 1, 1), color=None, overlay=True)
                for bbox, _text, _name, _offset, _destination in regions:
                    page.draw_rect(_source_clear_rect(bbox, source_spans), fill=(1, 1, 1), color=None, overlay=True)

                for bbox, text, region_name, vertical_offset, destination in regions:
                    text_rect = (fitz.Rect(destination) & page.rect) if destination else _expanded_text_rect(page, bbox, vertical_padding, vertical_offset)
                    if text_rect.is_empty:
                        raise PdfProcessingError(f"Hindi text placement for '{region_name}' is outside the page.")
                    source_page, ink = prepared[text]
                    fitted = _fit_text_rect(text_rect, ink, minimum_scale)
                    page.show_pdf_page(fitted, text_doc, source_page, clip=ink, overlay=True)

                for source, target in moves:
                    content = None
                    for span in source_spans:
                        rect = fitz.Rect(span["bbox"])
                        if ((rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2) in source:
                            content = rect if content is None else content | rect
                    if content is not None:
                        clip = content + (-0.25, -0.25, 0.25, 0.25)
                        fitted = _fit_text_rect(target, clip, minimum_scale)
                        dx = target.x0 - fitted.x0
                        fitted += (dx, 0, dx, 0)
                        page.show_pdf_page(fitted, original, page_index, clip=clip, overlay=True)

            doc.save(output_path, garbage=4, deflate=True)
    except PdfProcessingError:
        raise
    except (fitz.FileDataError, fitz.EmptyFileError, OSError, RuntimeError, ValueError) as error:
        raise PdfProcessingError("The PDF could not be updated with Hindi text.") from error
