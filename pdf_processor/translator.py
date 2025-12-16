import requests
import unicodedata

LIBRE_TRANSLATE_URL = "https://libretranslate.com/translate"

def translate_en_to_hi(text: str) -> str:
    if not text or not text.strip():
        return ""

    payload = {
        "q": text,
        "source": "en",
        "target": "hi",
        "format": "text"
    }

    response = requests.post(
        LIBRE_TRANSLATE_URL,
        data=payload,
        timeout=10
    )

    response.raise_for_status()

    hindi = response.json()["translatedText"]

    # Unicode normalization for correct Hindi rendering
    hindi = unicodedata.normalize("NFC", hindi)

    return hindi
