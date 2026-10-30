import logging
import math
import os
import shutil
import time
import uuid
from pathlib import Path

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from config_loader import load_config
from pdf_modifier import PdfProcessingError, apply_translations_to_pdf
from pdf_reader import PdfValidationError, get_pdf_info
from region_text_extractor import extract_text_from_regions
from region_translator import translate_regions
from translator import TranslationError


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "uploads"
CONFIG_PATH = BASE_DIR / "config.json"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_PDF_PAGES = 200
UPLOAD_TTL_SECONDS = 2 * 60 * 60

UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES + 1024 * 1024
allowed_origins = os.environ.get("CORS_ORIGINS", "*").split(",")
CORS(app, resources={r"/*": {"origins": [origin.strip() for origin in allowed_origins]}})
app.logger.setLevel(logging.INFO)


class ApiError(Exception):
    def __init__(self, message, status_code):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@app.errorhandler(ApiError)
def handle_api_error(error):
    return jsonify({"error": error.message}), error.status_code


@app.errorhandler(RequestEntityTooLarge)
def handle_large_upload(_error):
    return jsonify({"error": "The PDF is too large. Choose a file under 20 MB."}), 413


def get_job_directory(upload_id):
    if not upload_id:
        raise ApiError("Upload a PDF before starting this step.", 400)

    try:
        job_id = uuid.UUID(str(upload_id))
    except (ValueError, TypeError, AttributeError):
        raise ApiError("This upload session is invalid. Please upload the PDF again.", 400)

    job_dir = UPLOAD_FOLDER / str(job_id)
    if not job_dir.is_dir():
        raise ApiError("This upload session has expired. Please upload the PDF again.", 404)
    return job_dir


def get_uploaded_pdf(upload_id):
    job_dir = get_job_directory(upload_id)
    pdf_path = job_dir / "input.pdf"
    if not pdf_path.is_file():
        raise ApiError("The uploaded PDF could not be found. Please upload it again.", 404)
    return job_dir, pdf_path


def get_regions_and_options():
    try:
        config = load_config(CONFIG_PATH)
    except (OSError, ValueError) as error:
        app.logger.exception("Could not read the PDF conversion configuration")
        raise ApiError("The PDF conversion settings could not be loaded.", 500) from error

    regions = config.get("all_pages")
    if not isinstance(regions, list) or not regions:
        raise ApiError("The PDF conversion settings do not contain any text regions.", 500)

    for index, region in enumerate(regions):
        rect = region.get("rect") if isinstance(region, dict) else None
        if (
            not isinstance(region, dict)
            or not isinstance(region.get("name"), str)
            or not isinstance(rect, list)
            or len(rect) != 4
        ):
            raise ApiError(f"Text region {index + 1} is configured incorrectly.", 500)
        try:
            x0, y0, x1, y1 = (float(value) for value in rect)
        except (TypeError, ValueError):
            raise ApiError(f"Text region {index + 1} must use numeric coordinates.", 500)
        if not all(math.isfinite(value) for value in (x0, y0, x1, y1)):
            raise ApiError(f"Text region {index + 1} must use finite coordinates.", 500)
        if x0 >= x1 or y0 >= y1:
            raise ApiError(f"Text region {index + 1} has invalid boundaries.", 500)
        region["rect"] = [x0, y0, x1, y1]
        try:
            text_offset_y = float(region.get("text_offset_y", 0))
        except (TypeError, ValueError):
            raise ApiError(f"Text region {index + 1} has an invalid vertical text offset.", 500)
        if not math.isfinite(text_offset_y) or abs(text_offset_y) > 10:
            raise ApiError(f"Text region {index + 1} has an invalid vertical text offset.", 500)
        region["text_offset_y"] = text_offset_y

    text_options = config.get("pdf_text", {})
    if not isinstance(text_options, dict):
        raise ApiError("The PDF text settings are configured incorrectly.", 500)
    return regions, text_options


def remove_expired_uploads():
    cutoff = time.time() - UPLOAD_TTL_SECONDS
    for job_dir in UPLOAD_FOLDER.iterdir():
        if not job_dir.is_dir():
            continue
        try:
            uuid.UUID(job_dir.name)
        except ValueError:
            continue
        try:
            if job_dir.stat().st_mtime < cutoff:
                shutil.rmtree(job_dir, ignore_errors=True)
        except OSError:
            app.logger.warning("Could not inspect an expired upload session")


@app.route("/")
def index():
    return jsonify({"message": "BharatDocs PDF translation service is running."})


@app.route("/upload", methods=["POST"])
def upload_pdf():
    if "file" not in request.files:
        raise ApiError("Choose a PDF file to upload.", 400)

    uploaded_file = request.files["file"]
    original_name = secure_filename(uploaded_file.filename or "")
    if not original_name:
        raise ApiError("The file name is empty. Choose a PDF and try again.", 400)
    if Path(original_name).suffix.lower() != ".pdf":
        raise ApiError("Only PDF files can be translated.", 415)

    contents = uploaded_file.stream.read(MAX_UPLOAD_BYTES + 1)
    if len(contents) > MAX_UPLOAD_BYTES:
        raise ApiError("The PDF is too large. Choose a file under 20 MB.", 413)
    if b"%PDF-" not in contents[:1024]:
        raise ApiError("This file does not appear to be a valid PDF.", 415)

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
        raise ApiError(str(error), 422) from error

    if info["page_count"] > MAX_PDF_PAGES:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise ApiError(f"This PDF has more than {MAX_PDF_PAGES} pages. Split it into smaller files and try again.", 413)

    return jsonify({
        "message": "PDF uploaded successfully.",
        "upload_id": str(job_id),
        "filename": original_name,
        "page_count": info["page_count"],
    }), 201


@app.route("/verify-pdf", methods=["GET"])
def verify_pdf():
    _, pdf_path = get_uploaded_pdf(request.args.get("upload_id"))
    try:
        info = get_pdf_info(pdf_path)
    except PdfValidationError as error:
        raise ApiError(str(error), 422) from error

    if info["page_count"] > MAX_PDF_PAGES:
        raise ApiError(f"This PDF has more than {MAX_PDF_PAGES} pages.", 413)
    return jsonify({"message": "PDF is ready to translate.", **info})


@app.route("/extract-regions", methods=["GET"])
def extract_regions():
    _, pdf_path = get_uploaded_pdf(request.args.get("upload_id"))
    regions, _ = get_regions_and_options()
    try:
        extracted = extract_text_from_regions(pdf_path, regions)
    except PdfValidationError as error:
        raise ApiError(str(error), 422) from error
    return jsonify({"message": "Text was extracted from the configured regions.", "regions": extracted})


@app.route("/translate-regions", methods=["GET"])
def translate_regions_api():
    _, pdf_path = get_uploaded_pdf(request.args.get("upload_id"))
    regions, _ = get_regions_and_options()
    try:
        extracted = extract_text_from_regions(pdf_path, regions)
        translated = translate_regions(extracted)
    except PdfValidationError as error:
        raise ApiError(str(error), 422) from error
    except TranslationError as error:
        raise ApiError(str(error), 502) from error
    return jsonify({"message": "Text was translated into Hindi.", "data": translated})


@app.route("/translate-pdf", methods=["POST"])
def translate_pdf():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        raise ApiError("The upload session details are invalid. Please upload the PDF again.", 400)
    job_dir, pdf_path = get_uploaded_pdf(data.get("upload_id"))
    output_path = job_dir / "translated.pdf"
    regions, text_options = get_regions_and_options()

    try:
        info = get_pdf_info(pdf_path)
        if info["page_count"] > MAX_PDF_PAGES:
            raise ApiError(f"This PDF has more than {MAX_PDF_PAGES} pages.", 413)
        extracted = extract_text_from_regions(pdf_path, regions)
        translated = translate_regions(extracted)
        apply_translations_to_pdf(
            input_pdf_path=pdf_path,
            output_pdf_path=output_path,
            translated_regions=translated,
            text_options=text_options,
        )
    except ApiError:
        raise
    except PdfValidationError as error:
        raise ApiError(str(error), 422) from error
    except TranslationError as error:
        raise ApiError(str(error), 502) from error
    except PdfProcessingError as error:
        app.logger.exception("Could not create the translated PDF")
        raise ApiError("The Hindi text could not be placed in this PDF. Check the PDF regions and try again.", 422) from error
    except Exception as error:
        app.logger.exception("Unexpected PDF conversion failure")
        raise ApiError("The PDF could not be translated. Please try again.", 500) from error

    response = send_file(
        output_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name="translated_document.pdf",
        conditional=True,
    )
    response.call_on_close(lambda: shutil.rmtree(job_dir, ignore_errors=True))
    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
