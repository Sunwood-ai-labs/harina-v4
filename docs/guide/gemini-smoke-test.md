# Gemini Smoke Test

Use `app.gemini_smoke_test` when you want a quick receipt-recognition check against a few local dataset images before a larger migration or re-scan job.

## Best fit scenarios

- Confirm the configured Gemini model is responding correctly
- Validate prompt or schema changes before a full replay
- Check a fresh V1, V2, or V3 dataset export with about 2 images
- Save a lightweight verification artifact for team review

## Basic command

```bash
uv run harina dataset smoke-test --limit 2
```

The smoke test reads:

- `GEMINI_API_KEY`
- `GEMINI_TEST_MODEL`
- `DISCORD_DATASET_OUTPUT_DIR` as the default dataset root

This repository defaults to `gemini-2.5-flash` for smoke-test runs unless you override `GEMINI_TEST_MODEL`.
The always-on `bot run` and `drive watch` services continue to use `GEMINI_MODEL`.

## Common examples

Use the default dataset root and sample 2 unique images:

```bash
uv run harina dataset smoke-test --limit 2
```

Test a versioned migration dataset:

```bash
uv run harina dataset smoke-test --dataset-dir ./dataset/v3-backfill --limit 2
```

Save the output to a JSON artifact:

```bash
uv run harina dataset smoke-test --dataset-dir ./dataset/v3-backfill --limit 2 --output ./artifacts/gemini-smoke-test.json
```

Include duplicate files if you want to compare reposted images directly:

```bash
uv run harina dataset smoke-test --dataset-dir ./dataset/v3-backfill --limit 2 --allow-duplicates
```

## Output behavior

- Images are discovered recursively under the dataset directory
- Supported extensions include `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`, `.heic`, and `.heif`
- Duplicate files are skipped by SHA-256 hash unless `--allow-duplicates` is set
- The command prints a JSON summary with the selected files, hashes, and extracted fields
- `raw_text` is shortened into `raw_text_preview` to keep the smoke-test output readable

## Recommended verification flow

1. Export a small batch with `harina dataset download`.
2. Run `harina dataset smoke-test --limit 2`.
3. Review merchant, date, totals, and confidence in the JSON output.
4. If the result looks good, continue to the full backfill or replay job.
