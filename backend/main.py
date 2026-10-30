from __future__ import annotations

import logging
import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse
from starlette.status import HTTP_400_BAD_REQUEST
from starlette.middleware.cors import CORSMiddleware

from backend.api.routes import APIError, router
from backend.core.paths import resource_root


logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

app = FastAPI(
    title="BharatDocs API",
    description="Translate configured PDF regions into Hindi.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
)

allowed_origins = [
    origin.strip()
    for origin in os.environ.get("CORS_ORIGINS", "*").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)
app.include_router(router)


@app.exception_handler(APIError)
async def handle_api_error(_request: Request, error: APIError):
    return JSONResponse({"error": error.message}, status_code=error.status_code)


@app.exception_handler(RequestValidationError)
async def handle_request_validation(_request: Request, error: RequestValidationError):
    errors = error.errors()
    missing_file = any(tuple(item.get("loc", ())) == ("body", "file") for item in errors)
    message = (
        "Choose a PDF file to upload."
        if missing_file
        else "The upload session details are invalid. Please upload the PDF again."
    )
    return JSONResponse({"error": message}, status_code=HTTP_400_BAD_REQUEST)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok"}


frontend_directory = resource_root() / "frontend" / "out"
frontend_index = frontend_directory / "index.html"

if frontend_index.is_file():
    @app.get("/", include_in_schema=False)
    def frontend_homepage():
        return FileResponse(frontend_index)

    app.mount("/", StaticFiles(directory=frontend_directory, html=True), name="frontend")
else:
    @app.get("/", include_in_schema=False)
    def api_homepage():
        return {"message": "BharatDocs PDF translation API is running."}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        log_level=os.environ.get("LOG_LEVEL", "info").lower(),
    )
