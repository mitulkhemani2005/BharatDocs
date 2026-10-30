"""Local Hindi spelling for invoice names and addresses; never contacts a service."""

import json
import re
import threading
from functools import lru_cache

from backend.core.paths import resource_root


class TranslationError(Exception):
    """Raised when a field cannot be converted safely to Hindi."""


MODEL_DIRECTORY = resource_root() / "models" / "indicxlit-en-hi"
_lock = threading.Lock()
_tokens = re.compile(r"[A-Za-z0-9]+(?:['’][A-Za-z]+)?")
_initials = dict(zip("abcdefghijklmnopqrstuvwxyz", [
    "ए", "बी", "सी", "डी", "ई", "एफ", "जी", "एच", "आई", "जे", "के", "एल", "एम",
    "एन", "ओ", "पी", "क्यू", "आर", "एस", "टी", "यू", "वी", "डब्ल्यू", "एक्स", "वाई", "ज़ेड",
]))


@lru_cache(maxsize=1)
def _glossary():
    try:
        data = json.loads((resource_root() / "hindi_terms.json").read_text(encoding="utf-8"))
        terms = {key.casefold(): value for key, value in data.items()}
        if not terms or any(not key or not isinstance(value, str) or not value.strip() for key, value in terms.items()):
            raise ValueError("Invalid Hindi spelling dictionary")
        pattern = re.compile(
            r"(?<![A-Za-z0-9])(?:" + "|".join(re.escape(key) for key in sorted(terms, key=len, reverse=True)) + r")(?![A-Za-z0-9])",
            re.IGNORECASE,
        )
        return terms, pattern
    except (OSError, ValueError, TypeError, AttributeError) as error:
        raise TranslationError("The local Hindi spelling dictionary could not be loaded.") from error


@lru_cache(maxsize=1)
def _engine():
    if not (MODEL_DIRECTORY / "model.bin").is_file():
        raise TranslationError("The offline Hindi spelling model is missing. Reinstall BharatDocs or run scripts/prepare_offline_model.py.")
    try:
        import ctranslate2

        return ctranslate2.Translator(str(MODEL_DIRECTORY), device="cpu", compute_type="int8", inter_threads=1, intra_threads=2)
    except Exception as error:
        raise TranslationError("The offline Hindi spelling model could not be loaded.") from error


@lru_cache(maxsize=8192)
def _hindi_word(word):
    if len(word) == 1:
        return _initials[word.casefold()]
    if len(word) > 80:
        raise TranslationError("A name or address contains an unusually long word. Check its spelling.")
    try:
        with _lock:
            result = _engine().translate_batch(
                [["__hi__"] + list(word.casefold())], beam_size=5, max_decoding_length=160,
            )[0]
        output = "".join(result.hypotheses[0]).strip()
        if not output or re.search(r"[A-Za-z<>\ufffd]", output) or not re.search(r"[\u0900-\u097f]", output):
            raise ValueError("Invalid Hindi model output")
        return output
    except TranslationError:
        raise
    except Exception as error:
        raise TranslationError(f"Could not spell '{word}' in Hindi. Add its correct spelling to hindi_terms.json.") from error


def translate_to_hindi(text):
    if not isinstance(text, str):
        raise TypeError("Text to translate must be a string.")
    if not text.strip():
        return text
    terms, pattern = _glossary()
    converted = pattern.sub(lambda match: terms[match.group(0).casefold()], text)

    # House numbers, postcodes and mixed identifiers (e.g. 31B) stay exact.
    def convert(match):
        word = match.group(0)
        return word if any(char.isdigit() for char in word) else _hindi_word(word)

    converted = re.sub(r"\s*&\s*", " एवं ", _tokens.sub(convert, converted))
    return re.sub(r"[ \t]+", " ", converted).strip()
