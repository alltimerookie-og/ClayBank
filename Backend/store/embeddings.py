"""Local embedding model management."""

from __future__ import annotations

from pathlib import Path


MODEL_ID = "intfloat/multilingual-e5-small"
MODEL_DIRNAME = "multilingual-e5-small"


def model_directory(root: Path | None = None) -> Path:
    """Return the backend-owned embedding model directory."""
    base = root or Path(__file__).resolve().parents[1]
    directory = base / "models" / MODEL_DIRNAME
    directory.mkdir(parents=True, exist_ok=True)
    onnx_root = directory / "model.onnx"
    nested_onnx = directory / "onnx" / "model.onnx"
    nested_tokenizer = directory / "onnx" / "tokenizer.json"
    if not onnx_root.exists() and nested_onnx.exists():
        try:
            onnx_root.write_bytes(nested_onnx.read_bytes())
        except OSError:
            pass
    if not (directory / "tokenizer.json").exists() and nested_tokenizer.exists():
        try:
            (directory / "tokenizer.json").write_bytes(nested_tokenizer.read_bytes())
        except OSError:
            pass
    return directory


def is_downloaded(root: Path | None = None) -> bool:
    """Check whether the required ONNX and tokenizer files exist."""
    directory = model_directory(root)
    return (directory / "model.onnx").exists() and (directory / "tokenizer.json").exists()
