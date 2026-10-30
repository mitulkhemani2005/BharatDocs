from backend.services.translator import translate_to_hindi

def translate_regions(extracted_regions):
    translated = []

    for item in extracted_regions:
        hindi_text = translate_to_hindi(item["text"])

        translated.append({
            "page": item["page"],
            "region_name": item["region_name"],
            "rect": item["rect"],
            "text_offset_y": item.get("text_offset_y", 0),
            "english_text": item["text"],
            "hindi_text": hindi_text
        })

    return translated
