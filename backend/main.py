from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.status import HTTP_400_BAD_REQUEST
from starlette.middleware.cors import CORSMiddleware

from backend.api.routes import router
from backend.core.asyncio_errors import windows_disconnect_handler
from backend.core.errors import APIError


logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    with windows_disconnect_handler(asyncio.get_running_loop()):
        yield


app = FastAPI(
    title="BharatDocs API",
    description="Translate configured PDF regions into Hindi.",
    version="2.0.1",
    docs_url="/docs",
    redoc_url=None,
    lifespan=lifespan,
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
    invalid_configuration = any(tuple(item.get("loc", ())) == ("body", "configuration_id") for item in errors)
    message = (
        "Choose a PDF file to upload."
        if missing_file
        else "Create or select a saved configuration before translating a PDF."
        if invalid_configuration
        else str(errors[0].get("msg", "Check the submitted settings."))
    )
    return JSONResponse({"error": message}, status_code=HTTP_400_BAD_REQUEST)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def api_homepage():
    return {"service": "BharatDocs API", "status": "ok", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        log_level=os.environ.get("LOG_LEVEL", "info").lower(),
    )
