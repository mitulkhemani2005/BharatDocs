import html
from pathlib import Path

import fitz

from backend.core.paths import resource_root


FONT_DIRECTORY = resource_root() / "fonts"
FONT_FILES = {
    "Noto Sans Devanagari": "NotoSansDevanagari-Regular.ttf",
}
DEFAULT_TEXT_OPTIONS = {
    "font_family": "Noto Sans Devanagari",
    "font_size": 18,
    "vertical_padding": 2,
    "minimum_scale": 0.7,
}


class PdfProcessingError(Exception):
    """Raised when translated text cannot be safely rendered into the PDF."""


class LayoutSpaceError(PdfProcessingError):
    """A placement attempt needs a different allocation of page space."""


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

    if not 8 <= font_size <= 32:
        raise PdfProcessingError("Hindi PDF font size must be between 8 and 32 points.")
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


def _prepare_hindi_text(document, text, font_size, css, archive, wrap_width=None):
    """Shape once, then measure painted ink including every upper/lower matra."""
    page = document.new_page(width=(wrap_width + 4) if wrap_width else max(400, len(text) * font_size * 1.5), height=min(10000, max(font_size * 5, len(text) * font_size * 2)) if wrap_width else font_size * 5)
    if wrap_width:
        css = css.replace("white-space: nowrap", "white-space: normal; overflow-wrap: anywhere").replace("line-height: 1.5", "line-height: 1.6")
    remaining, _ = page.insert_htmlbox(
        page.rect + (2, 2, -2, -2), f'<p lang="hi">{html.escape(text, quote=False)}</p>',
        css=css, archive=archive, scale_low=1,
    )
    if remaining < 0:
        raise PdfProcessingError("This field contains more text than can fit on the PDF page.")
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
        raise LayoutSpaceError("The current placement needs more room for readable Hindi.")
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


def _subtract_rectangles(rectangle, masks):
    # Most invoice objects are nowhere near this field. Clip using plain numbers
    # and discard irrelevant/duplicate obstacles before creating any PDF objects.
    x0, y0, x1, y1 = rectangle
    pieces = [(x0, y0, x1, y1)]
    relevant = set()
    for mx0, my0, mx1, my1 in masks:
        if mx0 < x1 and mx1 > x0 and my0 < y1 and my1 > y0:
            relevant.add((max(mx0, x0), max(my0, y0), min(mx1, x1), min(my1, y1)))
    for mx0, my0, mx1, my1 in sorted(relevant):
        remaining = []
        for px0, py0, px1, py1 in pieces:
            ox0, oy0, ox1, oy1 = max(px0, mx0), max(py0, my0), min(px1, mx1), min(py1, my1)
            if ox0 >= ox1 or oy0 >= oy1:
                remaining.append((px0, py0, px1, py1))
                continue
            remaining.extend(part for part in (
                (px0, py0, px1, oy0), (px0, oy1, px1, py1),
                (px0, oy0, ox0, oy1), (ox1, oy0, px1, oy1),
            ) if part[0] < part[2] and part[1] < part[3])
        pieces = remaining
        if not pieces:
            break
    return [fitz.Rect(part) for part in pieces]


def _plan_selected_areas(page, regions, blockers, prepare):
    orders = [tuple(range(len(regions))),
              tuple(sorted(range(len(regions)), key=lambda i: regions[i][0].get_area() / max(1, len(regions[i][1])))),
              tuple(reversed(range(len(regions))))]
    failed_name = regions[0][2]
    failed_size = regions[0][3]
    for order in dict.fromkeys(orders):
        plans, placed = {}, []
        for index in order:
            bbox, text, name, font_size = regions[index]
            pieces = sorted(_subtract_rectangles(bbox, blockers + placed), key=lambda rect: rect.get_area(), reverse=True)
            found = None
            for piece in pieces:
                if piece.width < 2 or piece.height < 2:
                    continue
                for width in ((None, round(piece.width, 2)) if len(text) < 500 else (round(piece.width, 2),)):
                    try:
                        number, ink = prepare(text, width, font_size)
                    except PdfProcessingError:
                        continue
                    if ink.width > piece.width or ink.height > piece.height:
                        continue
                    fitted = _fit_text_rect(piece, ink, 1)
                    target_y = min(max((bbox.y0 + bbox.y1 - fitted.height) / 2, piece.y0), piece.y1 - fitted.height)
                    fitted += (0, target_y - fitted.y0, 0, target_y - fitted.y0)
                    found = (number, ink, fitted)
                    break
                if found:
                    break
            if found is None:
                failed_name = name
                failed_size = font_size
                break
            plans[index] = found
            placed.append(found[2] + (-.25, -.25, .25, .25))
        else:
            return plans
    raise LayoutSpaceError(
        f"Hindi text in '{failed_name}' on page {page.number + 1} cannot fit inside its selected area at {failed_size:g} pt. "
        "Increase that area's size or select a smaller font size."
    )


def apply_translations_to_pdf(input_pdf_path, output_pdf_path, translated_regions, text_options=None):
    font_family, font_size, _padding, _scale = _render_options(text_options)
    if not (FONT_DIRECTORY / FONT_FILES[font_family]).is_file():
        raise PdfProcessingError(f"The {font_family} font file is missing.")
    output_path = Path(output_pdf_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    archive = fitz.Archive(str(FONT_DIRECTORY))
    styles = {}
    try:
        with fitz.open(input_pdf_path) as doc, fitz.open() as shaped:
            if doc.needs_pass or doc.is_encrypted:
                raise PdfProcessingError("Password-protected PDFs cannot be translated.")
            for page in doc:
                if page.rotation:
                    page.remove_rotation()
            grouped, protected = {}, {}
            for region in translated_regions:
                index = region.get("page")
                if not isinstance(index, int) or not 0 <= index < len(doc):
                    continue
                protected.setdefault(index, set()).update(tuple(rect) for rect in region.get("protected_rects", []))
                text = region.get("hindi_text", "").strip()
                bbox = fitz.Rect(region["rect"]) & doc[index].rect
                if text and not bbox.is_empty:
                    override = region.get("font_size")
                    size = font_size if override is None else _render_options({"font_family": font_family, "font_size": override})[1]
                    grouped.setdefault(index, []).append((bbox, text, region.get("region_name", "Area"), size))
            prepared, failed, plans, clear_masks, spans_by_page = {}, set(), {}, {}, {}

            def prepare(text, width, size):
                key = (text, width, size)
                if key in failed:
                    raise LayoutSpaceError("This width cannot accommodate the selected text.")
                if key not in prepared:
                    try:
                        if size not in styles:
                            styles[size] = _font_css(font_family, size)
                        prepared[key] = _prepare_hindi_text(shaped, text, size, styles[size], archive, width)
                    except PdfProcessingError:
                        failed.add(key)
                        raise
                return prepared[key]

            # Shape every field first, then import resources without mutating shaped.
            for index, regions in grouped.items():
                page = doc[index]
                spans = [span for block in page.get_text("dict")["blocks"] for line in block.get("lines", []) for span in line["spans"]]
                spans_by_page[index] = spans
                blockers = [fitz.Rect(span["bbox"]) for span in spans if not any(
                    ((span["bbox"][0] + span["bbox"][2]) / 2, (span["bbox"][1] + span["bbox"][3]) / 2) in region[0] for region in regions)]
                blockers += [fitz.Rect(rect) for rect in protected.get(index, [])]
                for drawing in page.get_drawings():
                    for item in drawing["items"]:
                        if item[0] == "l":
                            blockers.append(fitz.Rect(item[1], item[2]).normalize() + (-.5, -.5, .5, .5))
                        elif item[0] == "re":
                            rect = fitz.Rect(item[1])
                            blockers.extend((fitz.Rect(rect.x0, rect.y0-.5, rect.x1, rect.y0+.5),
                                             fitz.Rect(rect.x0, rect.y1-.5, rect.x1, rect.y1+.5),
                                             fitz.Rect(rect.x0-.5, rect.y0, rect.x0+.5, rect.y1),
                                             fitz.Rect(rect.x1-.5, rect.y0, rect.x1+.5, rect.y1)))
                blockers.extend(fitz.Rect(info["bbox"]) for info in page.get_image_info())
                clear_masks[index] = blockers
                plans[index] = _plan_selected_areas(page, regions, blockers, prepare)

            for index, regions in grouped.items():
                page = doc[index]
                for bbox, _text, _name, _size in regions:
                    # Even English glyph cleanup cannot paint outside the chosen area.
                    clear = _source_clear_rect(bbox, spans_by_page[index]) & bbox
                    for piece in _subtract_rectangles(clear, clear_masks[index]):
                        page.draw_rect(piece, fill=(1, 1, 1), color=None, overlay=True)
                for number, ink, fitted in plans[index].values():
                    page.show_pdf_page(fitted, shaped, number, clip=ink, overlay=True)
            doc.save(output_path, garbage=4, deflate=True)
    except PdfProcessingError:
        raise
    except (fitz.FileDataError, fitz.EmptyFileError, OSError, RuntimeError, ValueError) as error:
        raise PdfProcessingError("The PDF could not be updated with Hindi text.") from error
