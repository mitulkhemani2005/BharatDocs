# BharatDocs - Offline English to Hindi PDF Converter

BharatDocs translates text from configured PDF regions into Hindi, writes the result back into a copy of the PDF, and lets the user preview or download it. The interface is designed for bills from New Durga Agencies, Ujjain.

## Features

- Drag-and-drop or browse to upload a PDF.
- Translate text from the configured regions into Hindi.
- Render Devanagari with the bundled Noto Sans Devanagari font and shaped text layout.
- Preserve detected numeric values and identifiers during translation.
- Preview and download the translated PDF.
- Keep each upload in a separate, short-lived session.
- Translate locally with a bundled English-to-Hindi model; user documents stay on the computer.
- Install the Windows desktop app once and use it without an internet connection.

## Requirements

- Python 3.10 or newer for development
- Node.js 20 or newer

People using the packaged Windows app do not need Python, Node.js, or internet access.

## Website and desktop app

The website and Windows app have separate build outputs. The website stays a normal Next.js app and runs in the browser. The desktop app opens its own window, serves its own static frontend, and starts a local offline backend.

### Website

Install and start the Flask backend from the project root:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -r model-build-requirements.txt
python scripts/prepare_offline_model.py
python app.py
```

In another terminal, install and start the Next.js frontend:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. In development, the frontend uses `http://localhost:5000` by default. Set `NEXT_PUBLIC_API_URL` to the hosted backend URL for the website deployment. `npm run build` (or `npm run build:web`) builds the website into Next.js's `.next` directory and does not create a static desktop export.

## Configure text regions

Edit `config.json` to change the rectangles that are translated. Coordinates are PDF points in `[x0, y0, x1, y1]` order. Each configured region is applied to every page.

The `pdf_text` section controls output typography:

```json
"pdf_text": {
  "font_family": "Mukta",
  "font_size": 14,
  "vertical_padding": 2,
  "minimum_scale": 0.7
}
```

An individual region may include `text_offset_y` to shift its Hindi line vertically while leaving the cleared source area unchanged.

The upload screen lets users choose Mukta SemiBold (recommended for print) or Noto Sans Devanagari. Both fonts are bundled locally for PDF output and Hindi interface text. Mukta is distributed under the SIL Open Font License; its license is included beside the font files. Keep these files when deploying.

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/` | Backend health check |
| `POST` | `/upload` | Validate and create an upload session; returns an `upload_id` |
| `GET` | `/verify-pdf?upload_id=...` | Return page count and encryption status |
| `GET` | `/extract-regions?upload_id=...` | Extract text from configured regions |
| `GET` | `/translate-regions?upload_id=...` | Return translated region text as JSON |
| `POST` | `/translate-pdf` | Accept `{"upload_id":"...","font_family":"Mukta"}` and return a translated PDF. `font_family` may be `Mukta` or `Noto Sans Devanagari`. |

Uploads must be valid, unencrypted PDFs under 20 MB and 200 pages. An upload session is isolated from other requests and is removed after PDF conversion; abandoned sessions are cleaned up after two hours.

## Deployment settings

- `PORT` sets the Flask listen port (default `5000`).
- `CORS_ORIGINS` is a comma-separated list of allowed frontend origins. It defaults to `*` for local development; set it to the deployed frontend origin in production.
- `NEXT_PUBLIC_API_URL` sets the backend URL used by the frontend.

The model preparation command downloads the pinned OPUS-MT English-to-Hindi model and converts it to a local CPU format. It requires internet access once during development. Afterward, `python app.py` and the desktop app translate without contacting a translation service. The website can continue using its configured hosted backend independently.

## Build the offline Windows installer

Build on a Windows x64 computer while online. The first build downloads the translation model and desktop packaging dependencies. The generated setup app includes the frontend, Python service, Hindi fonts, local translation model, and Electron runtime:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_offline_windows.ps1
```

The desktop frontend is built separately into `frontend\.next-desktop` and packaged as `resources\frontend\out`. The installer is written to `release\BharatDocs-Setup-1.0.0.exe`. Copy that installer to another Windows x64 computer, install it, and launch BharatDocs from its desktop shortcut. Internet is not required after installation. To rebuild without downloading or reconverting the model, use `-SkipModelPreparation` after the `models\opus-mt-en-hi` folder has already been prepared.

The app runs its service on a private loopback address on the same computer. PDFs are stored temporarily in the user's local application data folder and removed after conversion or when an abandoned upload expires.
