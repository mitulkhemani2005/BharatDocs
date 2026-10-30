import html
from pathlib import Path

import fitz

from app_paths import resource_root


FONT_DIRECTORY = resource_root() / "fonts"
FONT_FILES = {
    "Mukta": "Mukta-SemiBold.ttf",
    "Noto Sans Devanagari": "NotoSansDevanagari-Regular.ttf",
}
DEFAULT_TEXT_OPTIONS = {
    "font_family": "Mukta",
    "font_size": 14,
    "vertical_padding": 2,
    "minimum_scale": 0.8,
}


class PdfProcessingError(Exception):
    """Raised when translated text cannot be safely rendered into the PDF."""


def _render_options(options):
    options = {**DEFAULT_TEXT_OPTIONS, **(options or {})}
    font_family = options["font_family"]
    if not isinstance(font_family, str) or font_family not in FONT_FILES:
        raise PdfProcessingError("Choose Mukta or Noto Sans Devanagari for Hindi text.")
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
    css_weight = "600" if font_family == "Mukta" else "bold"
    return f"""
        @font-face {{
            font-family: 'PrintHindi';
            src: url('{filename}');
            font-weight: {css_weight};
        }}
        html, body, p {{
            font-family: 'PrintHindi';
            font-size: {font_size}pt;
            color: #111111;
            margin: 0;
            padding: 0;
        }}
        p {{
            text-align: center;
            font-weight: {css_weight};
            line-height: 1;
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

    try:
        with fitz.open(input_pdf_path) as doc:
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
                ))

            for page_index, regions in page_regions.items():
                page = doc[page_index]

                # Clear every target first so text from a neighboring region is never erased later.
                for bbox, _text, _name, _offset in regions:
                    page.draw_rect(bbox, fill=(1, 1, 1), color=None, overlay=True)

                for bbox, text, region_name, vertical_offset in regions:
                    text_rect = _expanded_text_rect(page, bbox, vertical_padding, vertical_offset)
                    markup = f'<p lang="hi">{html.escape(text, quote=False)}</p>'
                    spare_height, scale = page.insert_htmlbox(
                        text_rect,
                        markup,
                        css=css,
                        archive=archive,
                        scale_low=minimum_scale,
                        overlay=True,
                    )
                    if spare_height < 0 or scale < minimum_scale:
                        raise PdfProcessingError(
                            f"Hindi text does not fit in region '{region_name}' on page {page_index + 1}."
                        )

            doc.save(output_path, garbage=4, deflate=True)
    except PdfProcessingError:
        raise
    except (fitz.FileDataError, fitz.EmptyFileError, OSError, RuntimeError, ValueError) as error:
        raise PdfProcessingError("The PDF could not be updated with Hindi text.") from error
