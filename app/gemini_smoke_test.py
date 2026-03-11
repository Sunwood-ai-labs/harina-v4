from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import mimetypes
import os
from pathlib import Path

from dotenv import load_dotenv

from app.dataset_downloader import DEFAULT_OUTPUT_DIR
from app.gemini_client import GeminiReceiptExtractor


load_dotenv()


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".heic", ".heif"}


def parse_args() -> argparse.Namespace:
    default_dataset_dir = Path(os.getenv("DISCORD_DATASET_OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR)))
    parser = argparse.ArgumentParser(
        description="Run a quick Gemini receipt extraction smoke test against local dataset images."
    )
    parser.add_argument(
        "--dataset-dir",
        default=str(default_dataset_dir),
        help=f"Dataset root to scan recursively. Default: {default_dataset_dir}",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=2,
        help="Number of images to test. Default: 2",
    )
    parser.add_argument(
        "--allow-duplicates",
        action="store_true",
        help="Allow multiple identical files instead of deduplicating by content hash.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional path to write the JSON result summary.",
    )
    return parser.parse_args()


def is_supported_image_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES


def discover_dataset_images(dataset_dir: Path) -> list[Path]:
    if not dataset_dir.exists():
        raise RuntimeError(f"Dataset directory does not exist: {dataset_dir}")

    return sorted(path for path in dataset_dir.rglob("*") if is_supported_image_file(path))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def select_sample_images(paths: list[Path], *, limit: int, allow_duplicates: bool) -> list[Path]:
    if limit <= 0:
        raise ValueError("--limit must be greater than 0.")

    if allow_duplicates:
        return paths[:limit]

    selected: list[Path] = []
    seen_hashes: set[str] = set()
    for path in paths:
        digest = file_sha256(path)
        if digest in seen_hashes:
            continue
        seen_hashes.add(digest)
        selected.append(path)
        if len(selected) >= limit:
            break
    return selected


def preview_text(value: str | None, *, limit: int = 240) -> str | None:
    if value is None:
        return None
    return value[:limit]


async def run_smoke_test(args: argparse.Namespace) -> dict[str, object]:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Set GEMINI_API_KEY in your environment or .env before running the smoke test.")

    model = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview").strip() or "gemini-3-flash-preview"
    dataset_dir = Path(args.dataset_dir)
    candidates = discover_dataset_images(dataset_dir)
    selected = select_sample_images(candidates, limit=args.limit, allow_duplicates=args.allow_duplicates)

    if not selected:
        raise RuntimeError(f"No supported dataset images found under: {dataset_dir}")

    extractor = GeminiReceiptExtractor(api_key=api_key, model=model)

    results: list[dict[str, object]] = []
    for path in selected:
        mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        extraction = await extractor.extract(
            image_bytes=path.read_bytes(),
            mime_type=mime_type,
            filename=path.name,
        )
        payload = extraction.model_dump()
        payload["raw_text_preview"] = preview_text(payload.pop("raw_text", None))
        results.append(
            {
                "file": str(path.resolve()),
                "sha256": file_sha256(path),
                "result": payload,
            }
        )

    summary: dict[str, object] = {
        "model": model,
        "dataset_dir": str(dataset_dir.resolve()),
        "candidate_count": len(candidates),
        "requested_limit": args.limit,
        "selected_count": len(selected),
        "allow_duplicates": bool(args.allow_duplicates),
        "results": results,
    }

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    return summary


def main() -> None:
    args = parse_args()
    summary = asyncio.run(run_smoke_test(args))
    print(json.dumps(summary, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
