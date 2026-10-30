import re
import os
import threading
from functools import lru_cache

from app_paths import resource_root


class TranslationError(Exception):
    """Raised when the bundled offline translator cannot return Hindi text."""


MODEL_DIRECTORY = resource_root() / "models" / "opus-mt-en-hi"
_translator_lock = threading.Lock()
_code_pattern = re.compile(r"\b(?=[A-Z0-9/-]*[A-Z])(?=[A-Z0-9/-]*\d)[A-Z0-9/-]+\b", re.IGNORECASE)
_number_pattern = re.compile(r"(?<!\w)\d+(?:[.,/:_-]\d+)*(?!\w)")
_common_terms = {
    "amount": "राशि",
    "bank detail": "बैंक विवरण",
    "bill date": "बिल की तारीख",
    "bill no": "बिल नंबर",
    "gstin no": "जीएसटीआईएन नंबर",
    "labor": "मज़दूर",
    "labour": "मज़दूर",
    "labor wages": "मजदूरी",
    "labour wages": "मजदूरी",
    "net amount": "कुल राशि",
    "place of supply": "आपूर्ति का स्थान",
    "tax invoice": "कर बिल",
    "thank you": "धन्यवाद",
    "total amount": "कुल राशि",
    "wages": "मजदूरी",
    "worker": "मज़दूर",
    "workers": "मज़दूर",
}
_common_term_pattern = re.compile(
    r"^(?P<term>place\s+of\s+supply|total\s+amount|labor\s+wages|labour\s+wages|"
    r"thank\s+you|bank\s+detail|bill\s+date|bill\s+no|gstin\s+no|net\s+amount|tax\s+invoice|"
    r"amount|workers?|labor|labour|wages)"
    r"(?P<punctuation>[.!?,:]*)$",
    re.IGNORECASE,
)
_amount_line_pattern = re.compile(
    r"^(?P<label>total\s+amount|amount)(?P<separator>\s*[:\-]?\s*)"
    r"(?P<value>\d+(?:[.,/:_-]\d+)*)(?P<punctuation>[.!?]?)$",
    re.IGNORECASE,
)


def _looks_like_uppercase_name(text):
    letters = [character for character in text if character.isalpha()]
    words = re.findall(r"[A-Za-z]{2,}", text)
    return len(letters) > 0 and len(words) >= 2 and all(character.isupper() for character in letters)


@lru_cache(maxsize=1)
def _load_offline_translator():
    translation_dir = MODEL_DIRECTORY / "translation"
    tokenizer_dir = MODEL_DIRECTORY / "tokenizer"
    if not (translation_dir / "model.bin").is_file() or not (tokenizer_dir / "source.spm").is_file():
        raise TranslationError(
            "The offline Hindi model is missing. Reinstall BharatDocs or rebuild the app with its language model."
        )

    try:
        import ctranslate2
        from transformers import MarianTokenizer

        tokenizer = MarianTokenizer.from_pretrained(
            str(tokenizer_dir),
            local_files_only=True,
        )
        translator = ctranslate2.Translator(
            str(translation_dir),
            device="cpu",
            compute_type="int8",
            inter_threads=1,
            intra_threads=max(1, min(4, os.cpu_count() or 1)),
        )
        return tokenizer, translator
    except Exception as error:
        raise TranslationError("The bundled offline Hindi model could not be loaded on this computer.") from error


@lru_cache(maxsize=2048)
def _translate_text(text):
    try:
        tokenizer, translator = _load_offline_translator()
        source_ids = tokenizer.encode(text, add_special_tokens=True)
        source_tokens = tokenizer.convert_ids_to_tokens(source_ids)
        with _translator_lock:
            result = translator.translate_batch(
                [source_tokens],
                beam_size=3,
                max_decoding_length=256,
            )[0]
        target_ids = tokenizer.convert_tokens_to_ids(result.hypotheses[0])
        translated = tokenizer.decode(target_ids, skip_special_tokens=True).strip()
    except TranslationError:
        raise
    except Exception as error:
        raise TranslationError("Offline English-to-Hindi translation failed. Please try this PDF again.") from error

    if not translated:
        raise TranslationError("The offline translator returned an empty Hindi result.")
    return translated


def _translate_piece(piece):
    leading_whitespace = piece[: len(piece) - len(piece.lstrip())]
    trailing_whitespace = piece[len(piece.rstrip()) :]
    content = piece.strip()
    if not content:
        return piece

    amount_match = _amount_line_pattern.fullmatch(content)
    if amount_match:
        label = "कुल राशि" if amount_match.group("label").casefold().startswith("total") else "राशि"
        separator = ": " if ":" in amount_match.group("separator") else " "
        translated = f"{label}{separator}{amount_match.group('value')}{amount_match.group('punctuation')}"
        return leading_whitespace + translated + trailing_whitespace

    term_match = _common_term_pattern.fullmatch(content)
    if term_match:
        translated = _common_terms[term_match.group("term").casefold()]
        translated += term_match.group("punctuation")
        return leading_whitespace + translated + trailing_whitespace

    if _looks_like_uppercase_name(content):
        return leading_whitespace + content + trailing_whitespace

    numbers = list(_number_pattern.finditer(content))
    translated = _translate_text(content)
    translated_numbers = list(_number_pattern.finditer(translated))
    if numbers and len(numbers) == len(translated_numbers):
        for source_number, target_number in reversed(list(zip(numbers, translated_numbers))):
            translated = (
                translated[: target_number.start()]
                + source_number.group(0)
                + translated[target_number.end() :]
            )
    elif numbers:
        parts = []
        previous_end = 0
        for number in numbers:
            parts.append(_translate_text(content[previous_end : number.start()].strip()))
            parts.append(number.group(0))
            previous_end = number.end()
        parts.append(_translate_text(content[previous_end:].strip()))
        translated = " ".join(part for part in parts if part)
    return leading_whitespace + translated + trailing_whitespace


def translate_to_hindi(text):
    if not isinstance(text, str):
        raise TypeError("Text to translate must be a string.")
    if not text.strip():
        return text

    sentences = re.split(r"(?<=[.!?])(?=\s)|(?<=\n)", text)
    translated_sentences = []
    for sentence in sentences:
        pieces = []
        previous_end = 0
        for match in _code_pattern.finditer(sentence):
            pieces.append(_translate_piece(sentence[previous_end : match.start()]))
            pieces.append(match.group(0))
            previous_end = match.end()
        pieces.append(_translate_piece(sentence[previous_end:]))
        translated_sentences.append("".join(pieces))
    return "".join(translated_sentences).strip()
