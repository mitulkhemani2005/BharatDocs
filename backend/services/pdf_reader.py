from pathlib import Path

import fitz


class PdfValidationError(Exception):
    """Raised when an uploaded document cannot be processed as a PDF."""


def get_pdf_info(pdf_path):
    try:
        with fitz.open(Path(pdf_path)) as doc:
            if doc.needs_pass or doc.is_encrypted:
                raise PdfValidationError("This PDF is password protected. Remove the password and upload it again.")
            if doc.page_count < 1:
                raise PdfValidationError("This PDF does not contain any pages.")
            return {
                "page_count": doc.page_count,
                "is_encrypted": doc.is_encrypted,
            }
    except PdfValidationError:
        raise
    except (fitz.FileDataError, fitz.EmptyFileError, OSError, RuntimeError) as error:
        raise PdfValidationError("This PDF could not be opened. Make sure it is a valid, unprotected PDF.") from error
