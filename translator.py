import re
import threading
import time
from functools import lru_cache

from googletrans import Translator


class TranslationError(Exception):
    """Raised when the translation service cannot return usable Hindi text."""


_translator = Translator()
_translator_lock = threading.Lock()
_identifier_pattern = re.compile(
    r"\b(?=[A-Z0-9/-]*[A-Z])(?=[A-Z0-9/-]*\d)[A-Z0-9/-]+\b|(?<!\w)\d+(?:[.,/:_-]\d+)*(?!\w)",
    re.IGNORECASE,
)
_token_pattern = re.compile(r"ZXQNUM(\d{4})QXZ", re.IGNORECASE)


def _protect_identifiers(text):
    values = []

    def replace(match):
        token = f"ZXQNUM{len(values):04d}QXZ"
        values.append((token, match.group(0)))
        return token

    return _identifier_pattern.sub(replace, text), values


@lru_cache(maxsize=2048)
def _translate_protected_text(protected_text):
    translated_text = None
    last_error = None

    for attempt in range(2):
        try:
            with _translator_lock:
                translated_text = _translator.translate(protected_text, src="en", dest="hi").text
            break
        except Exception as error:  # network or provider errors vary by googletrans version
            last_error = error
            if attempt == 0:
                time.sleep(0.35)

    if not isinstance(translated_text, str) or not translated_text.strip():
        raise TranslationError("Hindi translation is temporarily unavailable. Check the internet connection and try again.") from last_error

    return translated_text


def translate_to_hindi(text):
    if not isinstance(text, str):
        raise TypeError("Text to translate must be a string.")
    if not text.strip():
        return text

    protected_text, protected_values = _protect_identifiers(text)
    translated_text = _translate_protected_text(protected_text)
    translated_tokens = [match.group(0).upper() for match in _token_pattern.finditer(translated_text)]
    expected_tokens = [token for token, _ in protected_values]
    if sorted(translated_tokens) != sorted(expected_tokens):
        raise TranslationError("The translation service changed a number or code. Please try again.")

    originals = {token: value for token, value in protected_values}

    def restore(match):
        return originals[match.group(0).upper()]

    return _token_pattern.sub(restore, translated_text).strip()
