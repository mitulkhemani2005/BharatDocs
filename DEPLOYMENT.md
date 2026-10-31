# Deployment

BharatDocs deploys its web frontend and API as separate services. The FastAPI root returns API status only. The desktop installer loads its static frontend directly and connects to a private loopback API.

## Docker Compose

Install Docker Desktop or Docker Engine with Compose. Copy `.env.example` to `.env`, then run:

```sh
docker compose up --build
```

The web client is available on port 3000 and the API on port 5000. The API stores accepted inputs and translated outputs in the persistent `bharatdocs_data` volume. The model is downloaded and checksum-verified while building the API image.

For a hosted web deployment, set `NEXT_PUBLIC_API_URL` to the public HTTPS URL of the API before building the web image, then set `CORS_ORIGINS` to the deployed web origin. The browser must be able to reach that API URL. Use persistent storage for `BHARATDOCS_DOCUMENTS` and back it up according to the operator's data policy.

The included Compose configuration is for development and private deployments. Before exposing the API publicly, put it behind the product's chosen authentication, request limits, HTTPS termination, and monitoring. The current API does not provide user accounts or request-rate limiting.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `PORT` | API listen port; defaults to `5000`. |
| `HOST` | API bind address; defaults to `127.0.0.1`. |
| `CORS_ORIGINS` | Comma-separated web origins allowed by the API. |
| `BHARATDOCS_DOCUMENTS` | Directory that contains `Input`, `Output`, and temporary `Work` folders. |
| `NEXT_PUBLIC_API_URL` | API base URL compiled into the web client. |

## GitHub Releases

The `Windows Release` workflow builds a Windows x64 installer when a `v*` tag is pushed. Keep the tag and `desktop/package.json` version aligned. The workflow publishes the setup executable and a SHA-256 checksum to the GitHub Release. Add `WINDOWS_CERTIFICATE` and `WINDOWS_CERTIFICATE_PASSWORD` repository secrets to code-sign public releases; without them, the installer remains unsigned.
