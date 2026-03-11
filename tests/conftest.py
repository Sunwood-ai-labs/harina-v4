from __future__ import annotations

from pathlib import Path

import pytest


def _find_dataset_image() -> Path:
    test_asset_root = Path(__file__).resolve().parents[1] / "docs" / "public" / "test"
    for path in sorted(test_asset_root.rglob("*")):
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}:
            return path
    raise RuntimeError(f"No test image found under: {test_asset_root}")


@pytest.fixture(scope="session")
def dataset_receipt_image_path() -> Path:
    return _find_dataset_image()


@pytest.fixture(scope="session")
def dataset_receipt_image_bytes(dataset_receipt_image_path: Path) -> bytes:
    return dataset_receipt_image_path.read_bytes()
