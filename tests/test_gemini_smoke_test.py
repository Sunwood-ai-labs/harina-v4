from pathlib import Path

from app.gemini_smoke_test import discover_dataset_images, select_sample_images


def test_discover_dataset_images_filters_supported_extensions(tmp_path: Path) -> None:
    (tmp_path / "a.jpg").write_bytes(b"jpg")
    (tmp_path / "b.png").write_bytes(b"png")
    (tmp_path / "notes.txt").write_text("ignore", encoding="utf-8")

    result = discover_dataset_images(tmp_path)

    assert result == [tmp_path / "a.jpg", tmp_path / "b.png"]


def test_select_sample_images_deduplicates_by_hash(tmp_path: Path) -> None:
    image_a = tmp_path / "a.jpg"
    image_b = tmp_path / "b.jpg"
    image_c = tmp_path / "c.jpg"
    image_a.write_bytes(b"same")
    image_b.write_bytes(b"same")
    image_c.write_bytes(b"different")

    result = select_sample_images([image_a, image_b, image_c], limit=2, allow_duplicates=False)

    assert result == [image_a, image_c]


def test_select_sample_images_can_keep_duplicates(tmp_path: Path) -> None:
    image_a = tmp_path / "a.jpg"
    image_b = tmp_path / "b.jpg"
    image_a.write_bytes(b"same")
    image_b.write_bytes(b"same")

    result = select_sample_images([image_a, image_b], limit=2, allow_duplicates=True)

    assert result == [image_a, image_b]


def test_discover_dataset_images_includes_real_dataset_image(dataset_receipt_image_path: Path) -> None:
    dataset_dir = Path(__file__).resolve().parents[1] / "docs" / "public" / "test"

    result = discover_dataset_images(dataset_dir)

    assert dataset_receipt_image_path in result


def test_select_sample_images_can_use_real_dataset_image(dataset_receipt_image_path: Path) -> None:
    result = select_sample_images([dataset_receipt_image_path], limit=1, allow_duplicates=False)

    assert result == [dataset_receipt_image_path]
