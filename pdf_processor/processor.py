import fitz
import json
import os
from PIL import Image, ImageDraw, ImageFont
from pdf_processor.translator import translate_en_to_hi


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
    # img = render_hindi_image("हिंदी टेक्स्ट", rect)
    hindi_text = translate_en_to_hi(text)
    img = render_hindi_image(hindi_text, rect)


    # Insert image into PDF
    page.insert_image(rect, stream=img)


# def render_hindi_image(text, rect):
#     width = int(rect.width)
#     height = int(rect.height)

#     img = Image.new("RGB", (width, height), "white")
#     draw = ImageDraw.Draw(img)
#     font = ImageFont.truetype(FONT_PATH, 8)

#     draw.text((2, 2), text, font=font, fill="black")

#     img_bytes = img_to_bytes(img)
#     return img_bytes
def render_hindi_image(text, rect):
    width = int(rect.width)
    height = int(rect.height)

    # Create blank image
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    # Start with a reasonable font size
    font_size = 12
    min_font_size = 8

    while font_size >= min_font_size:
        font = ImageFont.truetype(FONT_PATH, font_size)

        lines = wrap_text(draw, text, font, width - 6)
        line_height = font.getbbox("ह")[3] + 2
        total_text_height = line_height * len(lines)

        if total_text_height <= height - 4:
            break

        font_size -= 1

    # Draw text line by line
    y = 2
    for line in lines:
        draw.text((2, y), line, font=font, fill="black")
        y += line_height

    return img_to_bytes(img)

def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        test_line = current_line + (" " if current_line else "") + word
        bbox = draw.textbbox((0, 0), test_line, font=font)
        text_width = bbox[2] - bbox[0]

        if text_width <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return lines


def img_to_bytes(img):
    from io import BytesIO
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()