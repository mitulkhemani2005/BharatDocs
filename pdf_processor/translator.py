from googletrans import Translator
import unicodedata

_translator = Translator()

def translate_en_to_hi(text: str) -> str:
    if not text or not text.strip():
        return ""

    result = _translator.translate(text, src="en", dest="hi")
    hindi = result.text

    # Normalize Unicode (VERY important for Hindi)
    hindi = unicodedata.normalize("NFC", hindi)
    return hindi
