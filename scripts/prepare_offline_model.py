from __future__ import annotations

import shutil
import urllib.request
from pathlib import Path

from huggingface_hub import snapshot_download


ROOT = Path(__file__).resolve().parents[1]
MODEL_ROOT = ROOT / "models" / "opus-mt-en-hi"
MODEL_REVISION = "75d7f7c9232b2891c7d65fe4ef635616c72be867"
MODEL_REPO = "Helsinki-NLP/opus-mt-en-hi"
MODEL_LICENSE_URL = "https://www.apache.org/licenses/LICENSE-2.0.txt"


def main() -> None:
    print(f"Downloading the pinned {MODEL_REPO} model…", flush=True)
    snapshot = Path(
        snapshot_download(
            repo_id=MODEL_REPO,
            revision=MODEL_REVISION,
            local_dir=str(ROOT / ".build" / "opus-mt-en-hi-source"),
            allow_patterns=[
                "config.json",
                "generation_config.json",
                "pytorch_model.bin",
                "source.spm",
                "target.spm",
                "vocab.json",
                "tokenizer_config.json",
                "special_tokens_map.json",
                "README.md",
            ],
        )
    )

    tokenizer_dir = MODEL_ROOT / "tokenizer"
    translation_dir = MODEL_ROOT / "translation"
    tokenizer_dir.mkdir(parents=True, exist_ok=True)
    for filename in (
        "config.json",
        "source.spm",
        "target.spm",
        "vocab.json",
        "tokenizer_config.json",
        "special_tokens_map.json",
    ):
        source = snapshot / filename
        if source.is_file():
            shutil.copy2(source, tokenizer_dir / filename)

    print("Converting the model to compact CPU int8 format…", flush=True)
    from ctranslate2.converters import TransformersConverter

    TransformersConverter(str(snapshot)).convert(
        str(translation_dir),
        quantization="int8",
        force=True,
    )

    license_path = MODEL_ROOT / "LICENSE-OPUS-MT.txt"
    if not license_path.exists():
        with urllib.request.urlopen(MODEL_LICENSE_URL, timeout=30) as response:
            license_path.write_bytes(response.read())
    (MODEL_ROOT / "MODEL-NOTICE.txt").write_text(
        "English-to-Hindi translation model: Helsinki-NLP/opus-mt-en-hi\n"
        f"Pinned Hugging Face revision: {MODEL_REVISION}\n"
        "The model is identified as Apache-2.0 licensed on its Hugging Face model card.\n"
        "The CTranslate2 files in translation/ are converted and quantized from that model.\n"
        "Model card: https://huggingface.co/Helsinki-NLP/opus-mt-en-hi\n",
        encoding="utf-8",
    )
    size_mb = sum(path.stat().st_size for path in MODEL_ROOT.rglob("*") if path.is_file()) / (1024 * 1024)
    print(f"Offline Hindi model ready ({size_mb:.0f} MiB): {MODEL_ROOT}", flush=True)


if __name__ == "__main__":
    main()
