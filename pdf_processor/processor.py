import fitz
import json
import os
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_PATH = os.path.join(BASE_DIR, "fonts", "NotoSansDevanagari-Regular.ttf")
CONFIG_PATH = os.path.join(BASE_DIR, "pdf_processor", "config.json")


def process_pdf(input_pdf: str, output_pdf: str):
    doc = fitz.open(input_pdf)

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    total_pages = len(doc)

    if "all_pages" in config:
        for page_index in range(total_pages):
            page = doc[page_index]
            for field in config["all_pages"]:
                apply_rectangle(page, field)

    for page_key, fields in config.items():
        if page_key == "all_pages":
            continue
        page = doc[int(page_key)]
        for field in fields:
            apply_rectangle(page, field)

    doc.save(output_pdf)
    doc.close()


def apply_rectangle(page, field):
    rect = fitz.Rect(field["rect"])
    text = page.get_textbox(rect).strip()
    if not text:
        return

    # Clear original English text
    page.draw_rect(rect, fill=(1, 1, 1), overlay=True)

    # Render Hindi text to image
    img = render_hindi_image("हिंदी टेक्स्ट", rect)

    # Insert image into PDF
    page.insert_image(rect, stream=img)


def render_hindi_image(text, rect):
    width = int(rect.width)
    height = int(rect.height)

    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT_PATH, 18)

    draw.text((2, 2), text, font=font, fill="black")

    img_bytes = img_to_bytes(img)
    return img_bytes


def img_to_bytes(img):
    from io import BytesIO
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()