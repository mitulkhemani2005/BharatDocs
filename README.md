# BharatDocs - English to Hindi PDF Converter

BharatDocs translates text from configured PDF regions into Hindi, writes the result back into a copy of the PDF, and lets the user preview or download it. The interface is designed for bills from New Durga Agencies, Ujjain.

## Features

- Drag-and-drop or browse to upload a PDF.
- Translate text from the configured regions into Hindi.
- Render Devanagari with the bundled Noto Sans Devanagari font and shaped text layout.
- Preserve detected numeric values and identifiers during translation.
- Preview and download the translated PDF.
- Keep each upload in a separate, short-lived session.

## Requirements

- Python 3.10 or newer
- Node.js 20 or newer

## Run locally

Install and start the Flask backend from the project root:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

In another terminal, install and start the Next.js frontend:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. The frontend uses `http://localhost:5000` by default. Set `NEXT_PUBLIC_API_URL` before starting the frontend to use a different backend address.

## Configure text regions

Edit `config.json` to change the rectangles that are translated. Coordinates are PDF points in `[x0, y0, x1, y1]` order. Each configured region is applied to every page.

The `pdf_text` section controls output typography:

```json
"pdf_text": {
  "font_size": 14,
  "vertical_padding": 2,
  "minimum_scale": 0.8
}
```

An individual region may include `text_offset_y` to shift its Hindi line vertically while leaving the cleared source area unchanged.

The Noto font is stored in `fonts/NotoSansDevanagari-Regular.ttf` for PDF output and `frontend/public/fonts/` for Hindi interface text. Keep these files when deploying.

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/` | Backend health check |
| `POST` | `/upload` | Validate and create an upload session; returns an `upload_id` |
| `GET` | `/verify-pdf?upload_id=...` | Return page count and encryption status |
| `GET` | `/extract-regions?upload_id=...` | Extract text from configured regions |
| `GET` | `/translate-regions?upload_id=...` | Return translated region text as JSON |
| `POST` | `/translate-pdf` | Accept `{"upload_id":"..."}` and return a translated PDF |

Uploads must be valid, unencrypted PDFs under 20 MB and 200 pages. An upload session is isolated from other requests and is removed after PDF conversion; abandoned sessions are cleaned up after two hours.

## Deployment settings

- `PORT` sets the Flask listen port (default `5000`).
- `CORS_ORIGINS` is a comma-separated list of allowed frontend origins. It defaults to `*` for local development; set it to the deployed frontend origin in production.
- `NEXT_PUBLIC_API_URL` sets the backend URL used by the frontend.

The translation provider requires internet access. If translation is unavailable, the API returns a readable error so the user can retry.
