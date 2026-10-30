import fitz

from pdf_reader import PdfValidationError


def extract_text_from_regions(pdf_path, regions):
    results = []

    try:
        with fitz.open(pdf_path) as doc:
            if doc.needs_pass or doc.is_encrypted:
                raise PdfValidationError("This PDF is password protected. Remove the password and upload it again.")

            for page_index, page in enumerate(doc):
                for region in regions:
                    area = fitz.Rect(region["rect"]) & page.rect
                    collected = []
                    if not area.is_empty:
                        page_dict = page.get_text("dict", clip=area, sort=True)
                        spans = []
                        for block in page_dict["blocks"]:
                            if block.get("type") != 0:
                                continue
                            for line in block.get("lines", []):
                                for span in line.get("spans", []):
                                    text = span.get("text", "").strip()
                                    if text:
                                        spans.append((span["bbox"][1], span["bbox"][0], text))
                        spans.sort(key=lambda item: (item[0], item[1]))
                        collected = [text for _, _, text in spans]

                    results.append({
                        "page": page_index,
                        "region_name": region["name"],
                        "rect": region["rect"],
                        "text_offset_y": region.get("text_offset_y", 0),
                        "text": " ".join(collected),
                    })
    except PdfValidationError:
        raise
    except (fitz.FileDataError, fitz.EmptyFileError, OSError, RuntimeError) as error:
        raise PdfValidationError("This PDF could not be read. Make sure it is a valid, unprotected PDF.") from error

    return results
