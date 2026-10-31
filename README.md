# BharatDocs

**Offline English-to-Hindi PDF field translation for Windows and the web.**

[Download the Windows installer (v1.0.4)](https://github.com/mitulkhemani2005/BharatDocs/releases/download/v1.0.4/BharatDocs-Setup-1.0.4.exe) · [Release notes and checksum](https://github.com/mitulkhemani2005/BharatDocs/releases/tag/v1.0.4) · [All releases](https://github.com/mitulkhemani2005/BharatDocs/releases) · [License](LICENSE.txt) · [Terms](frontend/app/terms/page.tsx) · [Privacy](frontend/app/privacy/page.tsx)

[![CI](https://github.com/mitulkhemani2005/BharatDocs/actions/workflows/ci.yml/badge.svg)](https://github.com/mitulkhemani2005/BharatDocs/actions/workflows/ci.yml)

BharatDocs converts text in configured PDF fields to Hindi. It includes an offline Windows desktop app, a separate Next.js web client, and a FastAPI service. The web client and API run as independent services; the API root does not serve the frontend.

## About

BharatDocs is built for translating configured names, addresses, and other bill fields into readable Devanagari while retaining the surrounding PDF. It uses a local IndicXlit model and a bundled Hindi font. The Windows desktop app works offline after installation.

## Product

- Upload a PDF by browsing or drag and drop.
- Translate configured PDF regions into Hindi.
- Preview and download the translated PDF.
- Preserve numeric values and identifiers in configured text.
- Process translations locally in the Windows desktop app without an external translation API.
- Store desktop originals and translated copies in the user's Documents folder.

Create and select a saved configuration for your PDF layout before translating. The app translates names, addresses, and bill fields in those areas. Review translated names and amounts before using a document.

## Build the Windows installer

On a Windows x64 build machine with Python 3.10 and Node.js 20 or newer, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_offline_windows.ps1
```

The script prepares the pinned, checksum-verified translation model, builds the frontend and local API executable, and creates an NSIS installer in `release/`. The installer creates Start Menu and Desktop shortcuts with the BharatDocs icon. After installation, launch BharatDocs from either shortcut. Python, Node.js, and an internet connection are not needed on the target computer.

To rebuild with an already prepared model and installed Node dependencies:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_offline_windows.ps1 -SkipModelPreparation -SkipNodeInstall
```

## Run locally

Install Python 3.10 or newer and Node.js 20 or newer. In the project root:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts/prepare_offline_model.py
python -m uvicorn backend.main:app --host 127.0.0.1 --port 5000
```

In a second terminal, start the web client:

```powershell
cd frontend
npm ci
$env:NEXT_PUBLIC_API_URL = "http://127.0.0.1:5000"
npm run dev
```

Open `http://localhost:3000`. The API has health and OpenAPI endpoints at `http://127.0.0.1:5000/health` and `http://127.0.0.1:5000/docs`.

## Data storage

The desktop app saves accepted source PDFs to `Documents\BharatDocs\Input` and translated PDFs to `Documents\BharatDocs\Output`. Temporary working sessions are stored under `Documents\BharatDocs\Work`; expired sessions are pruned when a later upload begins. The input and output copies remain until the user removes them.

The web client cannot write to a visitor's local Documents folder. When deployed, the API stores its working files and retained copies on the server. Use a persistent, access-controlled volume and the `BHARATDOCS_DOCUMENTS` setting for that location.

## Deployment

Docker deployment files are provided for the API and web client. See [DEPLOYMENT.md](DEPLOYMENT.md) for local container deployment, environment variables, persistent storage, and public hosting requirements.

## Repository automation

- Install `requirements-dev.txt` to run the backend tests locally; it includes the HTTP client used by the API tests.
- GitHub Actions runs the backend unit suite, checks frontend types, and builds both frontend variants on pushes and pull requests.
- Pushing a version tag such as `v1.0.4` builds the Windows setup artifact and publishes a GitHub Release with a SHA-256 checksum.
- The release workflow expects the tag version to match `desktop/package.json`.
- Add the `WINDOWS_CERTIFICATE` and `WINDOWS_CERTIFICATE_PASSWORD` repository secrets to sign public Windows releases. Builds are unsigned when these secrets are not configured.

## Configure PDF regions

Use **New configuration** next to the configuration selector to create a reusable layout:

1. Enter a name and choose an original English PDF as a reference.
2. Select any reference page, then drag rectangles around the English fields to translate.
3. Select an area in the list to rename, redraw, or delete it. Use **Draw Hindi placement area** to leave extra room for matras or shift Hindi away from nearby labels.
4. Save the configuration, select it on the main screen, and upload a PDF to translate. The areas repeat on every page and scale proportionally with page size.
5. Use **Edit / delete** to update or remove a configuration, or **Save as new** to keep a separate copy.

Saved layouts are stored in `Documents/BharatDocs/Configurations/layouts.sqlite3` (or the configured `BHARATDOCS_DOCUMENTS` directory). They survive app restarts and work offline in the desktop app. The web app uses a random browser storage key to scope saved layouts on the API server; use the same browser to access them. Clearing browser storage loses that browser's association with its saved layouts. This key is not account authentication; public hosting still needs access controls as described in DEPLOYMENT.md.

The editor uses selectable PDF text, not OCR. Keep fields on separate lines in separate areas, and leave enough space for Hindi placement. Same-type rectangles cannot overlap. The last selected configuration is remembered in the browser.

The app starts with an empty configuration list. Create a configuration in the editor and select it before uploading a PDF for conversion. Deleting the selected configuration requires you to choose or create another one.

Hindi output uses the bundled Noto Sans Devanagari Regular font. The font is distributed under the SIL Open Font License. Keep its accompanying license when redistributing the font. Third-party component licenses are listed in `THIRD_PARTY_NOTICES.txt`.

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/` | API status |
| `GET` | `/health` | Health check |
| `POST` | `/upload` | Validate a PDF and create a short-lived processing session |
| `GET` | `/verify-pdf?upload_id=...` | Return page count and encryption status |
| `GET` | `/extract-regions?upload_id=...` | Extract configured text |
| `GET` | `/translate-regions?upload_id=...` | Translate configured text as JSON |
| `POST` | `/translate-pdf` | Create and return a translated PDF |
| `GET` | `/pdf-page?upload_id=...&page=1` | Render a reference page for drawing areas |
| `GET`, `POST` | `/configurations` | List or create saved configurations |
| `PUT`, `DELETE` | `/configurations/{id}` | Update or delete a saved configuration |

Configuration requests use the `X-Configuration-Owner` UUID header. A saved `configuration_id` is required in the `/translate-pdf` JSON body (or extraction endpoint query parameters) with the same header. Missing or deleted configurations are rejected; translation always uses the user's selected layout.

Uploads must be unencrypted PDFs under 20 MB and 200 pages. The API exposes OpenAPI documentation at `/docs`.

## Licensing

The BharatDocs application source is proprietary and all rights are reserved. Third-party components and bundled fonts remain under their respective licenses. See [LICENSE](LICENSE.txt) and `THIRD_PARTY_NOTICES.txt`.
