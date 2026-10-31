import fitz

from backend.services.pdf_reader import PdfValidationError


def extract_text_from_regions(pdf_path, regions):
    results = []

    try:
        with fitz.open(pdf_path) as doc:
            if doc.needs_pass or doc.is_encrypted:
                raise PdfValidationError("This PDF is password protected. Remove the password and upload it again.")

            for page_index, page in enumerate(doc):
                if page.rotation:
                    page.remove_rotation()
                scaled = []
                for region in regions:
                    region = dict(region)
                    if region.get("page_size"):
                        width, height = region["page_size"]
                        sx, sy = page.rect.width / width, page.rect.height / height
                        for key in ("rect", "text_rect"):
                            if region.get(key):
                                region[key] = [v * (sx if i % 2 == 0 else sy) for i, v in enumerate(region[key])]
                    scaled.append(region)
                protected = [fitz.Rect(r["rect"]) for r in scaled if r.get("mode") == "preserve"]
                seen = set()
                for region in scaled:
                    if region.get("mode") == "preserve":
                        continue
                    area = fitz.Rect(region["rect"]) & page.rect
                    collected = []
                    if not area.is_empty:
                        page_dict = page.get_text("rawdict", clip=area, sort=True)
                        spans = []
                        for block in page_dict["blocks"]:
                            if block.get("type") != 0:
                                continue
                            for line in block.get("lines", []):
                                for span in line.get("spans", []):
                                    chars = []
                                    for char in span.get("chars", []):
                                        key = (char["c"], *char["bbox"])
                                        if key in seen or any(fitz.Rect(char["bbox"]).intersects(mask) for mask in protected):
                                            chars.append(" ")
                                        else:
                                            chars.append(char["c"])
                                            seen.add(key)
                                    text = "".join(chars).strip()
                                    if text:
                                        spans.append((span["bbox"][1], span["bbox"][0], text))
                        spans.sort(key=lambda item: (item[0], item[1]))
                        collected = [text for _, _, text in spans]

                    results.append({
                        "page": page_index,
                        "region_name": region["name"],
                        "rect": region["rect"],
                        "text_rect": region.get("text_rect"),
                        "text_offset_y": region.get("text_offset_y", 0),
                        "font_size": region.get("font_size"),
                        "text": " ".join(collected),
                        "protected_rects": [list(rect) for rect in protected],
                    })
    except PdfValidationError:
        raise
    except (fitz.FileDataError, fitz.EmptyFileError, OSError, RuntimeError) as error:
        raise PdfValidationError("This PDF could not be read. Make sure it is a valid, unprotected PDF.") from error

    return results
