# BharatDocs

BharatDocs translates text from configured regions in PDF bills into Hindi, writes the result into a new PDF, and lets the user preview or download it. The web frontend is built with Next.js. The Python API is built with FastAPI.

## Features

- Drag-and-drop or browse to upload a PDF.
- Translate text from the configured regions into Hindi.
- Render Devanagari with the bundled Noto Sans Devanagari font and shaped text layout.
- Preserve detected numeric values and identifiers during translation.
- Preview and download the translated PDF.
- Keep each upload in a separate, short-lived session.
- Translate with Google Translate when it is available; use the bundled OPUS-MT model as an offline fallback.
- Keep using the Windows desktop app without an internet connection.
- Online translation sends only the extracted text from configured regions to Google. Offline translation stays on the computer.

## Requirements

- Python 3.10 or newer for development
- Node.js 20 or newer

People using the packaged Windows app do not need Python, Node.js, or internet access.

## Project layout

```text
backend/              FastAPI application, routes, and PDF/translation services
frontend/             Next.js website and desktop frontend
desktop/               Electron desktop shell
scripts/               Model preparation and Windows packaging
config.json            Active PDF regions and typography
config_examples/       Optional layout examples
```

The website and Windows app have separate frontend builds. The desktop app opens in its own window and starts a local backend.

## Run the website locally

Use Python 3.10 or newer and Node.js 20 or newer. If the offline model is not already present, prepare it once in a separate environment. This keeps the model-building packages, including PyTorch, out of the API runtime:

```powershell
cd D:\NDA_Converter
python -m venv .model-venv
.model-venv\Scripts\Activate.ps1
python -m pip install -r model-build-requirements.txt
python scripts/prepare_offline_model.py
deactivate
```

In the project root, create a clean environment for the FastAPI backend:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 5000
```

In a second terminal, start the Next.js website:

```powershell
cd D:\NDA_Converter\frontend
npm ci
$env:NEXT_PUBLIC_API_URL = "http://127.0.0.1:5000"
npm run dev
```

Open `http://localhost:3000`. The `NEXT_PUBLIC_API_URL` setting makes sure this frontend talks to your local FastAPI backend. Interactive API documentation is at `http://127.0.0.1:5000/docs`.

`npm run build` creates the Next.js website build. `npm run build:desktop` creates the separate static frontend used by the Electron app.

## Configure text regions

Edit `config.json` to change the rectangles that are translated. Coordinates are PDF points in `[x0, y0, x1, y1]` order. Each configured region is applied to every page.

The `pdf_text` section controls output typography:

```json
"pdf_text": {
  "font_family": "Noto Sans Devanagari",
  "font_size": 14,
  "vertical_padding": 2,
  "minimum_scale": 0.7
}
```

An individual region may include `text_offset_y` to shift its Hindi line vertically while leaving the cleared source area unchanged.

The PDF uses the bundled Noto Sans Devanagari Regular font at normal weight for clear, non-bold Hindi. The font is distributed under the SIL Open Font License; its license is included beside the font file. Keep the font and license when deploying.

## API

The FastAPI service exposes an OpenAPI schema at `/openapi.json` and interactive API documentation at `/docs`.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/` | Desktop frontend when packaged; API status in development |
| `GET` | `/health` | Backend health check |
| `POST` | `/upload` | Validate and create an upload session; returns an `upload_id` |
| `GET` | `/verify-pdf?upload_id=...` | Return page count and encryption status |
| `GET` | `/extract-regions?upload_id=...` | Extract text from configured regions |
| `GET` | `/translate-regions?upload_id=...` | Return translated region text as JSON |
| `POST` | `/translate-pdf` | Accept `{"upload_id":"...","font_family":"Noto Sans Devanagari"}` and return a translated PDF. |

Uploads must be valid, unencrypted PDFs under 20 MB and 200 pages. An upload session is isolated from other requests and is removed after PDF conversion; abandoned sessions are cleaned up after two hours.

## Deployment settings

- `PORT` sets the Uvicorn listen port (default `5000`).
- `HOST` sets the local backend bind address (default `127.0.0.1`).
- `CORS_ORIGINS` is a comma-separated list of allowed frontend origins. It defaults to `*` for local development; set it to the deployed frontend origin in production.
- `NEXT_PUBLIC_API_URL` sets the backend URL used by the frontend.

The deployment `Procfile` starts FastAPI with Uvicorn. The model preparation command downloads the pinned OPUS-MT English-to-Hindi model and converts it to a local CPU format. When Google Translate cannot be reached, the API uses this model locally. The alternate bill layout is preserved as `config_examples/second-bill.json`; `config.json` is the active layout.

## Build the offline Windows installer

Build on a Windows x64 computer while online. The first build downloads the translation model and desktop packaging dependencies. The generated setup app includes the frontend, Python service, Hindi fonts, local translation model, and Electron runtime:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_offline_windows.ps1
```

The desktop frontend is built separately into `frontend\.next-desktop` and packaged as `resources\frontend\out`. The installer is written to `release\BharatDocs-Setup-1.0.0.exe`. Copy that installer to another Windows x64 computer, install it, and launch BharatDocs from its desktop shortcut. Internet is not required after installation. To rebuild without downloading or reconverting the model, use `-SkipModelPreparation` after the `models\opus-mt-en-hi` folder has already been prepared.

The app runs its service on a private loopback address on the same computer. PDFs are stored temporarily in the user's local application data folder and removed after conversion or when an abandoned upload expires.
