"""Fetch verified English OCR data at setup/build time, never during conversion."""

import argparse
import hashlib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "models" / "tessdata"
REVISION = "87416418657359cb625c412a48b6e1d6d41c29bd"
FILES = {
    "eng.traineddata": "7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2",
    "LICENSE": "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    ROOT.mkdir(parents=True, exist_ok=True)
    for name, expected in FILES.items():
        target = ROOT / name
        if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == expected:
            continue
        if args.verify_only:
            raise RuntimeError(f"Offline OCR data is missing or invalid: {target}")
        temporary = target.with_suffix(target.suffix + ".download")
        try:
            print(f"Downloading offline OCR data: {name}", flush=True)
            urllib.request.urlretrieve(
                f"https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/{REVISION}/{name}", temporary,
            )
            if hashlib.sha256(temporary.read_bytes()).hexdigest() != expected:
                raise RuntimeError(f"Offline OCR checksum mismatch: {name}")
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    print(f"Verified offline English OCR data: {ROOT}", flush=True)


if __name__ == "__main__":
    main()
