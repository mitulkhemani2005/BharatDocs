from __future__ import annotations

import logging
import math
import shutil
import time
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel, ConfigDict
from starlette.background import BackgroundTask
from starlette.responses import FileResponse

from backend.core.config import load_config
from backend.core.paths import resource_root, user_data_root
from backend.services.pdf_modifier import PdfProcessingError, apply_translations_to_pdf
from backend.services.pdf_reader import PdfValidationError, get_pdf_info
from backend.services.region_text_extractor import extract_text_from_regions
from backend.services.region_translator import translate_regions
from backend.services.translator import TranslationError


logger = logging.getLogger(__name__)
router = APIRouter()

CONFIG_PATH = resource_root() / "config.json"
UPLOAD_FOLDER = user_data_root() / "uploads"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_PDF_PAGES = 200
UPLOAD_TTL_SECONDS = 2 * 60 * 60

UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)


class APIError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class TranslatePDFRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    upload_id: str
    font_family: Literal["Noto Sans Devanagari"] | None = None


def get_job_directory(upload_id: str | None) -> Path:
    if not upload_id:
        raise APIError("Upload a PDF before starting this step.", 400)

    try:
        job_id = uuid.UUID(str(upload_id))
    except (ValueError, TypeError, AttributeError) as error:
        raise APIError("This upload session is invalid. Please upload the PDF again.", 400) from error

    job_dir = UPLOAD_FOLDER / str(job_id)
    if not job_dir.is_dir():
        raise APIError("This upload session has expired. Please upload the PDF again.", 404)
    return job_dir


def get_uploaded_pdf(upload_id: str | None) -> tuple[Path, Path]:
    job_dir = get_job_directory(upload_id)
    pdf_path = job_dir / "input.pdf"
    if not pdf_path.is_file():
        raise APIError("The uploaded PDF could not be found. Please upload it again.", 404)
    return job_dir, pdf_path


def get_regions_and_options() -> tuple[list[dict], dict]:
    try:
        config = load_config(CONFIG_PATH)
    except (OSError, ValueError) as error:
        logger.exception("Could not read the PDF conversion configuration")
        raise APIError("The PDF conversion settings could not be loaded.", 500) from error

    regions = config.get("all_pages")
    if not isinstance(regions, list) or not regions:
        raise APIError("The PDF conversion settings do not contain any text regions.", 500)

    for index, region in enumerate(regions):
        rect = region.get("rect") if isinstance(region, dict) else None
        if (
            not isinstance(region, dict)
            or not isinstance(region.get("name"), str)
            or not isinstance(rect, list)
            or len(rect) != 4
        ):
            raise APIError(f"Text region {index + 1} is configured incorrectly.", 500)
        try:
            x0, y0, x1, y1 = (float(value) for value in rect)
        except (TypeError, ValueError) as error:
            raise APIError(f"Text region {index + 1} must use numeric coordinates.", 500) from error
        if not all(math.isfinite(value) for value in (x0, y0, x1, y1)):
            raise APIError(f"Text region {index + 1} must use finite coordinates.", 500)
        if x0 >= x1 or y0 >= y1:
            raise APIError(f"Text region {index + 1} has invalid boundaries.", 500)
        region["rect"] = [x0, y0, x1, y1]
        destination = region.get("text_rect")
        if destination is not None:
            try:
                if not isinstance(destination, list) or len(destination) != 4:
                    raise ValueError("Expected four coordinates")
                dx0, dy0, dx1, dy1 = (float(value) for value in destination)
                if not all(math.isfinite(value) for value in (dx0, dy0, dx1, dy1)) or dx0 >= dx1 or dy0 >= dy1:
                    raise ValueError("Invalid placement boundaries")
            except (TypeError, ValueError) as error:
                raise APIError(f"Text region {index + 1} has an invalid Hindi text_rect.", 500) from error
            region["text_rect"] = [dx0, dy0, dx1, dy1]
        try:
            text_offset_y = float(region.get("text_offset_y", 0))
        except (TypeError, ValueError) as error:
            raise APIError(f"Text region {index + 1} has an invalid vertical text offset.", 500) from error
        if not math.isfinite(text_offset_y) or abs(text_offset_y) > 10:
            raise APIError(f"Text region {index + 1} has an invalid vertical text offset.", 500)
        region["text_offset_y"] = text_offset_y

    text_options = config.get("pdf_text", {})
    if not isinstance(text_options, dict):
        raise APIError("The PDF text settings are configured incorrectly.", 500)
    return regions, text_options


def remove_expired_uploads() -> None:
    cutoff = time.time() - UPLOAD_TTL_SECONDS
    for job_dir in UPLOAD_FOLDER.iterdir():
        if not job_dir.is_dir():
            continue
        try:
            uuid.UUID(job_dir.name)
            if job_dir.stat().st_mtime < cutoff:
                shutil.rmtree(job_dir, ignore_errors=True)
        except ValueError:
            continue
        except OSError:
            logger.warning("Could not inspect an expired upload session")


def safe_filename(filename: str | None) -> str:
    basename = (filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not basename:
        raise APIError("The file name is empty. Choose a PDF and try again.", 400)
    if Path(basename).suffix.lower() != ".pdf":
        raise APIError("Only PDF files can be translated.", 415)
    return basename


@router.post("/upload", status_code=201)
async def upload_pdf(file: UploadFile = File(...)):
    filename = safe_filename(file.filename)
    contents = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(contents) > MAX_UPLOAD_BYTES:
        raise APIError("The PDF is too large. Choose a file under 20 MB.", 413)
    if b"%PDF-" not in contents[:1024]:
        raise APIError("This file does not appear to be a valid PDF.", 415)

    remove_expired_uploads()
    job_id = uuid.uuid4()
    job_dir = UPLOAD_FOLDER / str(job_id)
    job_dir.mkdir(parents=True)
    pdf_path = job_dir / "input.pdf"
    pdf_path.write_bytes(contents)

    try:
        info = get_pdf_info(pdf_path)
    except PdfValidationError as error:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise APIError(str(error), 422) from error

    if info["page_count"] > MAX_PDF_PAGES:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise APIError(f"This PDF has more than {MAX_PDF_PAGES} pages. Split it into smaller files and try again.", 413)

    return {
        "message": "PDF uploaded successfully.",
        "upload_id": str(job_id),
        "filename": filename,
        "page_count": info["page_count"],
    }


@router.get("/verify-pdf")
def verify_pdf(upload_id: str | None = None):
    _, pdf_path = get_uploaded_pdf(upload_id)
    try:
        info = get_pdf_info(pdf_path)
    except PdfValidationError as error:
        raise APIError(str(error), 422) from error

    if info["page_count"] > MAX_PDF_PAGES:
        raise APIError(f"This PDF has more than {MAX_PDF_PAGES} pages.", 413)
    return {"message": "PDF is ready to translate.", **info}


@router.get("/extract-regions")
def extract_regions(upload_id: str | None = None):
    _, pdf_path = get_uploaded_pdf(upload_id)
    regions, _ = get_regions_and_options()
    try:
        extracted = extract_text_from_regions(pdf_path, regions)
    except PdfValidationError as error:
        raise APIError(str(error), 422) from error
    return {"message": "Text was extracted from the configured regions.", "regions": extracted}


@router.get("/translate-regions")
def translate_regions_api(upload_id: str | None = None):
    _, pdf_path = get_uploaded_pdf(upload_id)
    regions, _ = get_regions_and_options()
    try:
        extracted = extract_text_from_regions(pdf_path, regions)
        translated = translate_regions(extracted)
    except PdfValidationError as error:
        raise APIError(str(error), 422) from error
    except TranslationError as error:
        raise APIError(str(error), 502) from error
    return {"message": "Text was translated into Hindi.", "data": translated}


@router.post("/translate-pdf")
def translate_pdf(payload: TranslatePDFRequest):
    job_dir, pdf_path = get_uploaded_pdf(payload.upload_id)
    output_path = job_dir / "translated.pdf"
    regions, text_options = get_regions_and_options()
    if payload.font_family:
        text_options["font_family"] = payload.font_family

    try:
        info = get_pdf_info(pdf_path)
        if info["page_count"] > MAX_PDF_PAGES:
            raise APIError(f"This PDF has more than {MAX_PDF_PAGES} pages.", 413)
        extracted = extract_text_from_regions(pdf_path, regions)
        translated = translate_regions(extracted)
        apply_translations_to_pdf(
            input_pdf_path=pdf_path,
            output_pdf_path=output_path,
            translated_regions=translated,
            text_options=text_options,
        )
    except APIError:
        raise
    except PdfValidationError as error:
        raise APIError(str(error), 422) from error
    except TranslationError as error:
        raise APIError(str(error), 502) from error
    except PdfProcessingError as error:
        logger.warning("Could not create the translated PDF: %s", error)
        raise APIError(str(error), 422) from error
    except Exception as error:
        logger.exception("Unexpected PDF conversion failure")
        raise APIError("The PDF could not be translated. Please try again.", 500) from error

    return FileResponse(
        output_path,
        media_type="application/pdf",
        filename="translated_document.pdf",
        background=BackgroundTask(shutil.rmtree, job_dir, ignore_errors=True),
    )
