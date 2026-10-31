from __future__ import annotations

import logging
import base64
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Literal

import fitz
from fastapi import APIRouter, File, UploadFile, Header, Query
from pydantic import BaseModel, ConfigDict, Field
from starlette.responses import FileResponse

from backend.core.errors import APIError
from backend.services import configurations
from backend.core.paths import user_documents_root
from backend.services.pdf_modifier import PdfProcessingError, apply_translations_to_pdf
from backend.services.pdf_reader import PdfValidationError, get_pdf_info
from backend.services.region_text_extractor import extract_text_from_regions
from backend.services.region_translator import translate_regions
from backend.services.translator import TranslationError


logger = logging.getLogger(__name__)
router = APIRouter()

DOCUMENTS_FOLDER = user_documents_root()
UPLOAD_FOLDER = DOCUMENTS_FOLDER / "Work"
INPUT_FOLDER = DOCUMENTS_FOLDER / "Input"
OUTPUT_FOLDER = DOCUMENTS_FOLDER / "Output"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_PDF_PAGES = 200
UPLOAD_TTL_SECONDS = 2 * 60 * 60

for folder in (UPLOAD_FOLDER, INPUT_FOLDER, OUTPUT_FOLDER):
    folder.mkdir(parents=True, exist_ok=True)


class TranslatePDFRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    upload_id: str
    configuration_id: str = Field(min_length=1)
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


def get_regions_and_options(configuration_id=None, owner=None) -> tuple[list[dict], dict]:
    if not configuration_id:
        raise APIError("Create or select a saved configuration before translating a PDF.", 400)
    config = configurations.conversion_settings(owner, configuration_id)
    return config["all_pages"], config["pdf_text"]


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
    stem = Path(basename).stem
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", stem).strip(" .") or "document"
    return f"{stem}.pdf"


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

    saved_input = INPUT_FOLDER / f"{job_id.hex[:8]}_{filename}"
    shutil.copy2(pdf_path, saved_input)
    (job_dir / "filename.txt").write_text(filename, encoding="utf-8")

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


@router.get("/pdf-page")
def pdf_page(upload_id: str, page: int = Query(default=1, ge=1, le=MAX_PDF_PAGES)):
    _, path = get_uploaded_pdf(upload_id)
    with fitz.open(path) as document:
        if page > len(document):
            raise APIError("This page does not exist in the PDF.", 400)
        source = document[page - 1]
        if source.rotation:
            # Preview and extraction both use the visible, upright page coordinates.
            source.remove_rotation()
        scale = min(2, 1600 / max(source.rect.width, source.rect.height))
        image = source.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        return {"page": page, "page_count": len(document), "width": source.rect.width,
                "height": source.rect.height, "image": "data:image/png;base64," + base64.b64encode(image.tobytes("png")).decode("ascii")}


@router.get("/configurations")
def list_configurations(x_configuration_owner: str | None = Header(default=None)):
    return {"configurations": configurations.list_layouts(x_configuration_owner)}


@router.post("/configurations", status_code=201)
def create_configuration(payload: configurations.Layout, x_configuration_owner: str | None = Header(default=None)):
    return configurations.save_layout(x_configuration_owner, payload)


@router.put("/configurations/{configuration_id}")
def update_configuration(configuration_id: str, payload: configurations.Layout, x_configuration_owner: str | None = Header(default=None)):
    return configurations.save_layout(x_configuration_owner, payload, configuration_id)


@router.delete("/configurations/{configuration_id}")
def delete_configuration(configuration_id: str, x_configuration_owner: str | None = Header(default=None)):
    configurations.delete_layout(x_configuration_owner, configuration_id)
    return {"message": "Configuration deleted."}


@router.get("/extract-regions")
def extract_regions(upload_id: str | None = None, configuration_id: str | None = None, x_configuration_owner: str | None = Header(default=None)):
    _, pdf_path = get_uploaded_pdf(upload_id)
    regions, _ = get_regions_and_options(configuration_id, x_configuration_owner)
    try:
        extracted = extract_text_from_regions(pdf_path, regions)
    except PdfValidationError as error:
        raise APIError(str(error), 422) from error
    return {"message": "Text was extracted from the configured regions.", "regions": extracted}


@router.get("/translate-regions")
def translate_regions_api(upload_id: str | None = None, configuration_id: str | None = None, x_configuration_owner: str | None = Header(default=None)):
    _, pdf_path = get_uploaded_pdf(upload_id)
    regions, _ = get_regions_and_options(configuration_id, x_configuration_owner)
    try:
        extracted = extract_text_from_regions(pdf_path, regions)
        if not any(region["text"].strip() for region in extracted):
            raise APIError("No selectable text was found in these areas. Edit the configuration and select the English text. Scanned PDFs need OCR first.", 422)
        translated = translate_regions(extracted)
    except PdfValidationError as error:
        raise APIError(str(error), 422) from error
    except TranslationError as error:
        raise APIError(str(error), 502) from error
    return {"message": "Text was translated into Hindi.", "data": translated}


@router.post("/translate-pdf")
def translate_pdf(payload: TranslatePDFRequest, x_configuration_owner: str | None = Header(default=None)):
    job_dir, pdf_path = get_uploaded_pdf(payload.upload_id)
    job_id = uuid.UUID(str(payload.upload_id))
    source_name = (job_dir / "filename.txt").read_text(encoding="utf-8").strip() or "document.pdf"
    output_filename = f"Hindi_{job_id.hex[:8]}_{source_name}"
    output_path = OUTPUT_FOLDER / output_filename
    regions, text_options = get_regions_and_options(payload.configuration_id, x_configuration_owner)
    if payload.font_family:
        text_options["font_family"] = payload.font_family

    try:
        info = get_pdf_info(pdf_path)
        if info["page_count"] > MAX_PDF_PAGES:
            raise APIError(f"This PDF has more than {MAX_PDF_PAGES} pages.", 413)
        extracted = extract_text_from_regions(pdf_path, regions)
        if not any(region["text"].strip() for region in extracted):
            raise APIError("No selectable text was found in these areas. Edit the configuration and select the English text. Scanned PDFs need OCR first.", 422)
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
        filename=output_filename,
    )
