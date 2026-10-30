"""Download verified, ready-to-run IndicXlit assets at build time only."""

import argparse
import hashlib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_ROOT = ROOT / "models" / "indicxlit-en-hi"
MODEL_REPO = "Singla0009/all-indic-transliteration"
MODEL_REVISION = "23279e441f195f6a45296fcee84ac89b541254ff"
FILES = {
    "config.json": "fd782624788113fe180ddc1b8973919be65a77aa5654ef6edf96b6910b20b1a9",
    "model.bin": "22b088a2dc8c1566204eb72f49db2d7e4db8d4444af290945b96927d023525aa",
    "source_vocabulary.json": "051af9821496ccf0ba9ba08ca6027ef7c990d7483799f5850b8d6bac9c37da1a",
    "target_vocabulary.json": "5048e07cb417975e80fdd5a243d00e40ffa21f91900950cd4c675ed0e937b160",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true", help="Verify existing assets without network access")
    args = parser.parse_args()
    MODEL_ROOT.mkdir(parents=True, exist_ok=True)
    for name, expected in FILES.items():
        destination = MODEL_ROOT / name
        if destination.is_file() and hashlib.sha256(destination.read_bytes()).hexdigest() == expected:
            continue
        if args.verify_only:
            raise RuntimeError(f"Offline model file is missing or invalid: {destination}")
        temporary = destination.with_suffix(destination.suffix + ".download")
        try:
            url = f"https://huggingface.co/{MODEL_REPO}/resolve/{MODEL_REVISION}/indicxlit_ct2_fp32/{name}"
            print(f"Downloading offline Hindi model: {name}", flush=True)
            urllib.request.urlretrieve(url, temporary)
            if hashlib.sha256(temporary.read_bytes()).hexdigest() != expected:
                raise RuntimeError(f"Offline model checksum mismatch: {name}")
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
    print(f"Verified offline Hindi spelling model: {MODEL_ROOT}", flush=True)


if __name__ == "__main__":
    main()
