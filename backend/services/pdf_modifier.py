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


def _automatic_destination(page, seed, blockers, font_size):
    """Grow into nearby blank space, respecting labels, rules and other fields."""
    top, bottom = max(0, seed.y0 - font_size * 2), min(page.rect.height, seed.y1 + font_size * 2)
    for block in blockers:
        if block.x0 < seed.x1 and block.x1 > seed.x0:
            if block.y1 <= seed.y0:
                top = max(top, block.y1 + 1)
            elif block.y0 >= seed.y1:
                bottom = min(bottom, block.y0 - 1)
    expanded = fitz.Rect(seed.x0, top, seed.x1, bottom)
    pieces = _subtract_rectangles(expanded, blockers)
    if not pieces:
        raise LayoutSpaceError("The current placement has no free space.")
    return max(pieces, key=lambda rect: rect.get_area())


def _plan_page(page, regions, seeds, fixed, masks, font_size, prepare, redistribute=False):
    """Retry the entire group so a tight field can borrow unused neighboring space."""
    group = fitz.Rect(seeds[0])
    for seed in seeds[1:]:
        group |= seed
    group = (group + (-font_size * 2, -font_size * 4, font_size * 2, font_size * 4)) & page.rect
    orders = [list(range(len(regions)))]
    if redistribute:
        orders = [sorted(orders[0], key=lambda i: seeds[i].get_area() / max(1, len(regions[i][1]))), orders[0], list(reversed(orders[0]))]
    orders = list(dict.fromkeys(tuple(order) for order in orders))
    for order in orders:
        placed, result = [], {}
        for index in order:
            text = regions[index][1]
            blockers = fixed + masks + placed
            if not redistribute:
                blockers += [seed for i, seed in enumerate(seeds) if i != index]
            destinations = []
            try:
                destinations.append(_automatic_destination(page, seeds[index], blockers, font_size))
            except LayoutSpaceError:
                pass
            if redistribute:
                # Selected areas are movable space, not permanent obstacles. Search
                # all free pieces in their shared neighborhood before shrinking.
                destinations += _subtract_rectangles(group, blockers)
                destinations = sorted(destinations, key=lambda rect: rect.get_area(), reverse=True)[:24]
            candidates = []
            ideal_fit = False
            for destination in destinations:
                if destination.width < 8 or destination.height < 8:
                    continue
                widths = (None, round(destination.width, 2)) if len(text) < 500 else (round(destination.width, 2),)
                for width in widths:
                    try:
                        number, ink = prepare(text, width)
                    except PdfProcessingError:
                        # An oversized paragraph can be paginated by the continuation
                        # path; failing a single shaping attempt must not abort it.
                        continue
                    scale = min(1, destination.width / ink.width, destination.height / ink.height)
                    if scale + 1e-6 < min(1, 8 / font_size):
                        continue
                    fitted = _fit_text_rect(destination, ink, min(1, 8 / font_size) - 1e-6)
                    target_y = min(max((seeds[index].y0 + seeds[index].y1 - fitted.height) / 2, destination.y0), destination.y1 - fitted.height)
                    dy = target_y - fitted.y0
                    fitted += (0, dy, 0, dy)
                    ordered = True
                    for other_index, (_, _, other_rect) in result.items():
                        other_seed = seeds[other_index]
                        if min(seeds[index].x1, other_seed.x1) <= max(seeds[index].x0, other_seed.x0):
                            continue
                        if seeds[index].y0 >= other_seed.y1 and fitted.y0 < other_rect.y1 + 1:
                            ordered = False
                        elif seeds[index].y1 <= other_seed.y0 and fitted.y1 + 1 > other_rect.y0:
                            ordered = False
                    if not ordered:
                        continue
                    distance = math.hypot(fitted.x0 - seeds[index].x0, fitted.y0 - seeds[index].y0)
                    candidates.append((scale - distance / max(1, page.rect.width + page.rect.height) * .15, number, ink, fitted))
                    if scale >= .95:
                        ideal_fit = True
                        break
                if ideal_fit:
                    break
            if not candidates:
                break
            _, number, ink, fitted = max(candidates, key=lambda item: item[0])
            result[index] = (number, ink, fitted)
            placed.append(fitted + (-1, -1, 1, 1))
        else:
            return result
    raise LayoutSpaceError("The selected fields need a Hindi continuation page.")


def _continuation_chunks(text, limit=300):
    words, chunk = text.split(), []
    size = 0
    for word in words:
        if chunk and size + len(word) > limit:
            yield " ".join(chunk)
            chunk, size = [], 0
        chunk.append(word)
        size += len(word) + 1
    if chunk:
        yield " ".join(chunk)


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
            protected_pages = {}
            for region in translated_regions:
                page_index = region.get("page")
                if not isinstance(page_index, int) or not 0 <= page_index < doc.page_count:
                    continue
                protected_pages[page_index] = [fitz.Rect(rect) for rect in region.get("protected_rects", [])]
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

            # Plan and shape everything before grafting PDF resources from text_doc.
            plans = {}
            clear_masks = {}
            overflow = {}
            continuation_plans = []
            failed_shapes = set()

            def prepare(text, width=None):
                key = (text, width)
                if key in failed_shapes:
                    raise LayoutSpaceError("This shaping width has already been tried.")
                if key not in prepared:
                    try:
                        prepared[key] = _prepare_hindi_text(text_doc, text, font_size, css, archive, width)
                    except PdfProcessingError:
                        failed_shapes.add(key)
                        raise
                return prepared[key]

            for page_index, regions in page_regions.items():
                page = doc[page_index]
                masks = protected_pages.get(page_index, [])
                spans = [fitz.Rect(span["bbox"]) for block in page.get_text("dict")["blocks"]
                         for line in block.get("lines", []) for span in line["spans"]]
                fixed = [span for span in spans if not any(
                    ((span.x0 + span.x1) / 2, (span.y0 + span.y1) / 2) in item[0] for item in regions)]
                # Thin rules and image bounds are also content to avoid.
                for drawing in page.get_drawings():
                    for item in drawing["items"]:
                        if item[0] == "l":
                            line = fitz.Rect(item[1], item[2]).normalize()
                            fixed.append(line + (-.5, -.5, .5, .5))
                        elif item[0] == "re":
                            rect = fitz.Rect(item[1])
                            fixed.extend((fitz.Rect(rect.x0, rect.y0-.5, rect.x1, rect.y0+.5),
                                          fitz.Rect(rect.x0, rect.y1-.5, rect.x1, rect.y1+.5),
                                          fitz.Rect(rect.x0-.5, rect.y0, rect.x0+.5, rect.y1),
                                          fitz.Rect(rect.x1-.5, rect.y0, rect.x1+.5, rect.y1)))
                fixed.extend(fitz.Rect(info["bbox"]) for info in page.get_image_info())
                clear_masks[page_index] = fixed + masks
                seeds = [fitz.Rect(item[4]) if item[4] else fitz.Rect(item[0]) for item in regions]
                try:
                    page_plan = _plan_page(page, regions, seeds, fixed, masks, font_size, prepare)
                except LayoutSpaceError:
                    try:
                        page_plan = _plan_page(page, regions, seeds, fixed, masks, font_size, prepare, redistribute=True)
                    except LayoutSpaceError:
                        # Keep this original bill intact and provide every Hindi field
                        # at full size on labeled continuation pages. Never drop text.
                        overflow[page_index] = regions
                        continue
                plans.update({(page_index, index): placement for index, placement in page_plan.items()})

            # Finish shaping every continuation page before importing text_doc resources.
            for original_index, regions in overflow.items():
                target_index, cursor = None, 0
                for _bbox, text, name, _offset, _destination in regions:
                    for chunk_index, chunk in enumerate(_continuation_chunks(text)):
                        content = f"{name}: {chunk}" if chunk_index == 0 else chunk
                        number, ink = prepare(content, 535)
                        if target_index is None or cursor + ink.height > 810:
                            target = doc.new_page(width=595, height=842)
                            target_index, cursor = target.number, 64
                            heading, heading_ink = prepare(f"हिंदी विवरण - मूल पृष्ठ {original_index + 1}", 535)
                            header = fitz.Rect(30, 25, 30 + heading_ink.width, 25 + heading_ink.height)
                            continuation_plans.append((target_index, heading, heading_ink, header))
                        fitted = fitz.Rect(30, cursor, 30 + ink.width, cursor + ink.height)
                        continuation_plans.append((target_index, number, ink, fitted))
                        cursor = fitted.y1 + 14

            for page_index, regions in page_regions.items():
                if page_index in overflow:
                    continue
                page = doc[page_index]

                # Clear every target first so text from a neighboring region is never erased later.
                source_spans = [span for block in page.get_text("dict")["blocks"]
                                for line in block.get("lines", []) for span in line["spans"]]
                for source, target in moves:
                    if not page.rect.contains(source) or not page.rect.contains(target):
                        raise PdfProcessingError("A PDF move_regions rectangle is outside the page.")
                    page.draw_rect(source, fill=(1, 1, 1), color=None, overlay=True)
                for bbox, _text, _name, _offset, _destination in regions:
                    for clear in _subtract_rectangles(_source_clear_rect(bbox, source_spans), clear_masks.get(page_index, [])):
                        page.draw_rect(clear, fill=(1, 1, 1), color=None, overlay=True)

                for index, _region in enumerate(regions):
                    source_page, ink, fitted = plans[(page_index, index)]
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

            for target_index, number, ink, fitted in continuation_plans:
                doc[target_index].show_pdf_page(fitted, text_doc, number, clip=ink, overlay=True)

            doc.save(output_path, garbage=4, deflate=True)
    except PdfProcessingError:
        raise
    except (fitz.FileDataError, fitz.EmptyFileError, OSError, RuntimeError, ValueError) as error:
        raise PdfProcessingError("The PDF could not be updated with Hindi text.") from error
