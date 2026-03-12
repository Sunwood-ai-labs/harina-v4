import asyncio
from pathlib import Path
from types import SimpleNamespace

from app.test_asset_runner import discover_test_cases, discover_test_images, run_test_asset_suite


def test_discover_test_images_filters_supported_extensions(tmp_path: Path) -> None:
    (tmp_path / "a.jpg").write_bytes(b"jpg")
    (tmp_path / "b.png").write_bytes(b"png")
    (tmp_path / "notes.txt").write_text("ignore", encoding="utf-8")

    result = discover_test_images(tmp_path)

    assert result == [tmp_path / "a.jpg", tmp_path / "b.png"]


def test_discover_test_cases_prefers_subdirectories(tmp_path: Path) -> None:
    one_dir = tmp_path / "one"
    two_dir = tmp_path / "two"
    one_dir.mkdir()
    two_dir.mkdir()
    (one_dir / "IMG_1.jpg").write_bytes(b"a")
    (two_dir / "IMG_2.jpg").write_bytes(b"b")
    (two_dir / "IMG_3.png").write_bytes(b"c")

    result = discover_test_cases(tmp_path)

    assert [(case.name, len(case.image_paths)) for case in result] == [("one", 1), ("two", 2)]


def test_run_test_asset_suite_runs_cli_and_discord_by_case(monkeypatch, tmp_path: Path) -> None:
    one_dir = tmp_path / "one"
    two_dir = tmp_path / "two"
    one_dir.mkdir()
    two_dir.mkdir()
    image_a = one_dir / "IMG_1.jpg"
    image_b = two_dir / "IMG_2.png"
    image_c = two_dir / "IMG_3.jpg"
    image_a.write_bytes(b"a")
    image_b.write_bytes(b"b")
    image_c.write_bytes(b"c")

    cli_calls: list[Path] = []
    discord_calls: list[tuple[int, list[Path], str, float]] = []

    async def fake_run_local_receipt_process(**kwargs):
        cli_calls.append(kwargs["image_path"])
        return {
            "image_path": str(kwargs["image_path"]),
            "mime_type": "image/jpeg",
            "google_write_performed": False,
        }

    async def fake_run_discord_upload_test(*, settings, channel_id, image_paths, caption, timeout_seconds, image_path=None):
        del settings, image_path
        discord_calls.append((channel_id, image_paths, caption, timeout_seconds))
        return {
            "channel_id": channel_id,
            "image_paths": [str(path) for path in image_paths],
            "thread_id": 999,
            "reply_message_urls": ["https://discord.test/thread"],
        }

    monkeypatch.setattr("app.test_asset_runner.run_local_receipt_process", fake_run_local_receipt_process)
    monkeypatch.setattr("app.test_asset_runner.run_discord_upload_test", fake_run_discord_upload_test)

    summary = asyncio.run(
        run_test_asset_suite(
            settings=SimpleNamespace(discord_test_channel_id=123456),
            source_dir=tmp_path,
            mode="both",
            discord_timeout_seconds=12.5,
        )
    )

    assert cli_calls == [image_a, image_b, image_c]
    assert discord_calls == [
        (123456, [image_a], "docs/public/test/one", 12.5),
        (123456, [image_b, image_c], "docs/public/test/two", 12.5),
    ]
    assert summary["case_count"] == 2
    assert summary["success"] is True
    assert summary["cli_result_count"] == 2
    assert summary["cli_failure_count"] == 0
    assert summary["discord_result_count"] == 2
    assert summary["discord_failure_count"] == 0
    assert summary["cases"][0]["image_count"] == 1
    assert summary["cases"][1]["image_count"] == 2
    assert summary["cli_results"][0]["case"] == "one"
    assert summary["discord_results"][1]["case"] == "two"


def test_run_test_asset_suite_collects_errors_and_continues(monkeypatch, tmp_path: Path) -> None:
    one_dir = tmp_path / "one"
    two_dir = tmp_path / "two"
    one_dir.mkdir()
    two_dir.mkdir()
    image_a = one_dir / "IMG_1.jpg"
    image_b = two_dir / "IMG_2.png"
    image_c = two_dir / "IMG_3.jpg"
    image_a.write_bytes(b"a")
    image_b.write_bytes(b"b")
    image_c.write_bytes(b"c")

    async def fake_run_local_receipt_process(**kwargs):
        if kwargs["image_path"] == image_a:
            raise RuntimeError("gemini busy")
        return {
            "image_path": str(kwargs["image_path"]),
            "mime_type": "image/png",
            "google_write_performed": False,
        }

    async def fake_run_discord_upload_test(*, settings, channel_id, image_paths, caption, timeout_seconds, image_path=None):
        del settings, channel_id, caption, timeout_seconds, image_path
        if len(image_paths) == 2:
            raise RuntimeError("timeout")
        return {
            "image_paths": [str(path) for path in image_paths],
            "thread_id": 999,
        }

    monkeypatch.setattr("app.test_asset_runner.run_local_receipt_process", fake_run_local_receipt_process)
    monkeypatch.setattr("app.test_asset_runner.run_discord_upload_test", fake_run_discord_upload_test)

    summary = asyncio.run(
        run_test_asset_suite(
            settings=SimpleNamespace(discord_test_channel_id=123456),
            source_dir=tmp_path,
            mode="both",
        )
    )

    assert summary["success"] is False
    assert summary["cli_failure_count"] == 1
    assert summary["discord_failure_count"] == 1
    assert summary["cli_results"][0]["results"][0]["status"] == "error"
    assert summary["discord_results"][1]["status"] == "error"
