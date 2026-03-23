# Release QA Inventory

## Release Context

- repository: `harina-v4`
- release tag: `v4.4.0`
- compare range: `v4.3.0..v4.4.0`
- requested outputs: GitHub release body, docs-backed release notes, companion walkthrough article
- validation commands run: `uv run pytest`, `npm --prefix docs run docs:build`, `powershell -ExecutionPolicy Bypass -File D:\Prj\gh-release-notes-skill\scripts\verify-svg-assets.ps1 -RepoPath . -Path docs/public/brand/harina-hero-v4.4.0.svg`, `gh run view 23431498075 --json status,conclusion,url,headSha,workflowName`, `gh run view 23431498113 --json status,conclusion,url,headSha,workflowName`, `gh release view v4.4.0 --json url,name,body,publishedAt,targetCommitish`
- release URLs: `https://github.com/Sunwood-ai-labs/harina-v4/releases/tag/v4.4.0`, `https://sunwood-ai-labs.github.io/harina-v4/guide/release-notes-v4.4.0`, `https://sunwood-ai-labs.github.io/harina-v4/guide/whats-new-v4.4.0`, `https://sunwood-ai-labs.github.io/harina-v4/ja/guide/release-notes-v4.4.0`, `https://sunwood-ai-labs.github.io/harina-v4/ja/guide/whats-new-v4.4.0`

## Claim Matrix

| claim | code refs | validation refs | docs surfaces touched | scope |
| --- | --- | --- | --- | --- |
| Formula-driven `Analysis YYYY` and `Analysis All Years` dashboards plus on-demand `google sync-analysis` shipped in v4.4.0 | `app/cli.py`, `app/google_workspace.py`, `tests/test_cli.py`, `tests/test_google_workspace.py` | `uv run pytest`, `gh run view 23431498075 --json status,conclusion,url,headSha,workflowName`, `gh release view v4.4.0 --json url,name,body,publishedAt,targetCommitish` | `README.md`, `README.ja.md`, `docs/guide/overview.md`, `docs/ja/guide/overview.md`, `docs/guide/cli.md`, `docs/ja/guide/cli.md`, `docs/guide/google-setup.md`, `docs/ja/guide/google-setup.md` | steady_state |
| Spreadsheet-side duplicate review and persistent `重複確認` auto-exclusion controls shipped without mutating raw yearly receipt tabs | `app/google_workspace.py`, `tests/test_google_workspace.py` | `uv run pytest`, `gh run view 23431498075 --json status,conclusion,url,headSha,workflowName`, `gh release view v4.4.0 --json url,name,body,publishedAt,targetCommitish` | `README.md`, `README.ja.md`, `docs/guide/overview.md`, `docs/ja/guide/overview.md`, `docs/guide/google-setup.md`, `docs/ja/guide/google-setup.md` | steady_state |
| Discord `/resume_polling` shipped as a Drive watcher operator command with scoped wait clearing and docs guidance | `app/drive_watcher.py`, `tests/test_drive_watcher.py`, `docs/guide/deployment.md`, `docs/ja/guide/deployment.md` | `uv run pytest`, `gh run view 23431498075 --json status,conclusion,url,headSha,workflowName`, `gh release view v4.4.0 --json url,name,body,publishedAt,targetCommitish` | `README.md`, `README.ja.md`, `docs/guide/cli.md`, `docs/ja/guide/cli.md`, `docs/guide/deployment.md`, `docs/ja/guide/deployment.md` | path_specific |
| Docs-backed release collateral, bilingual walkthroughs, nav updates, and a versioned hero asset were shipped before the tag and are live | `docs/guide/release-notes-v4.4.0.md`, `docs/guide/whats-new-v4.4.0.md`, `docs/ja/guide/release-notes-v4.4.0.md`, `docs/ja/guide/whats-new-v4.4.0.md`, `docs/public/brand/harina-hero-v4.4.0.svg`, `docs/.vitepress/config.mts` | `npm --prefix docs run docs:build`, `powershell -ExecutionPolicy Bypass -File D:\Prj\gh-release-notes-skill\scripts\verify-svg-assets.ps1 -RepoPath . -Path docs/public/brand/harina-hero-v4.4.0.svg`, `gh run view 23431498113 --json status,conclusion,url,headSha,workflowName`, `Invoke-WebRequest` live URL checks, `git merge-base --is-ancestor 37ea2abb1bbe0985de9c2ef25c198a724db74c51 v4.4.0` | `docs/index.md`, `docs/ja/index.md`, `docs/.vitepress/config.mts`, `docs/guide/release-notes-v4.4.0.md`, `docs/ja/guide/release-notes-v4.4.0.md`, `docs/guide/whats-new-v4.4.0.md`, `docs/ja/guide/whats-new-v4.4.0.md` | release_collateral |

## Steady-State Docs Review

| surface | status | evidence |
| --- | --- | --- |
| README.md | pass | Updated release-facing overview and operator links for dashboards, duplicate review, and `/resume_polling` |
| README.ja.md | pass | Synced Japanese release-facing overview and operator links for dashboards, duplicate review, and `/resume_polling` |
| docs/guide/overview.md | pass | Added v4.4.0 dashboard and duplicate-review behavior to the steady-state overview |
| docs/ja/guide/overview.md | pass | Synced the Japanese overview with the v4.4.0 dashboard and duplicate-review behavior |
| docs/guide/cli.md | pass | Added `google sync-analysis` and `/resume_polling` operator guidance |
| docs/ja/guide/cli.md | pass | Synced the Japanese CLI guide with `google sync-analysis` and `/resume_polling` guidance |
| docs/guide/google-setup.md | pass | Added dashboard rebuild and duplicate-control sheet guidance |
| docs/ja/guide/google-setup.md | pass | Synced the Japanese Google setup guide with dashboard rebuild and duplicate-control guidance |
| docs/guide/deployment.md | pass | Added release-relevant Drive watcher operator guidance for `/resume_polling` |
| docs/ja/guide/deployment.md | pass | Synced the Japanese deployment guide with `/resume_polling` guidance |
| docs/index.md | pass | Updated the latest-release entry point to v4.4.0 collateral |
| docs/ja/index.md | pass | Updated the Japanese latest-release entry point to v4.4.0 collateral |
| docs/.vitepress/config.mts | pass | Updated nav/sidebar links so the release collateral is discoverable from the docs shell |
| docs/guide/release-notes-v4.4.0.md | pass | Created the English docs-backed release notes page |
| docs/ja/guide/release-notes-v4.4.0.md | pass | Created the Japanese docs-backed release notes page |
| docs/guide/whats-new-v4.4.0.md | pass | Created the English companion walkthrough article |
| docs/ja/guide/whats-new-v4.4.0.md | pass | Created the Japanese companion walkthrough article |

## QA Inventory

| criterion_id | status | evidence |
| --- | --- | --- |
| compare_range | pass | `powershell -ExecutionPolicy Bypass -File D:\Prj\gh-release-notes-skill\scripts\collect-release-context.ps1 -Tag v4.4.0` resolved `v4.3.0..v4.4.0` |
| release_claims_backed | pass | Claim matrix ties release body claims to `app/cli.py`, `app/drive_watcher.py`, `app/google_workspace.py`, and the matching tests/docs files |
| docs_release_notes | pass | `docs/guide/release-notes-v4.4.0.md`, `docs/ja/guide/release-notes-v4.4.0.md` |
| companion_walkthrough | pass | `docs/guide/whats-new-v4.4.0.md`, `docs/ja/guide/whats-new-v4.4.0.md` |
| operator_claims_extracted | pass | Release body, release-note pages, walkthrough pages, README, overview, CLI, setup, and deployment docs were reviewed and mapped in the claim matrix |
| impl_sensitive_claims_verified | pass | Verified analysis/dashboard behavior against `app/google_workspace.py` + tests, and `/resume_polling` behavior against `app/drive_watcher.py` + `tests/test_drive_watcher.py`; CI run `23431498075` passed on tag target `3a718bbd5d43f2c748e7485a1ad15a8f9a787994` |
| steady_state_docs_reviewed | pass | Reviewed and updated the surfaces listed in the Steady-State Docs Review table, including both READMEs and primary operator docs |
| claim_scope_precise | pass | Release text scopes `google sync-analysis` to dashboard rebuilds, scopes duplicate controls to spreadsheet analysis, and scopes `/resume_polling` to Drive watcher waits instead of all Discord commands |
| latest_release_links_updated | pass | `README.md`, `README.ja.md`, `docs/index.md`, `docs/ja/index.md`, and `docs/.vitepress/config.mts` all point at v4.4.0 collateral |
| svg_assets_validated | pass | `powershell -ExecutionPolicy Bypass -File D:\Prj\gh-release-notes-skill\scripts\verify-svg-assets.ps1 -RepoPath . -Path docs/public/brand/harina-hero-v4.4.0.svg` returned `SVG assets look valid.` |
| docs_assets_committed_before_tag | pass | Release collateral commit `37ea2abb1bbe0985de9c2ef25c198a724db74c51` is an ancestor of `v4.4.0` (`git merge-base --is-ancestor 37ea2abb1bbe0985de9c2ef25c198a724db74c51 v4.4.0` -> success) |
| docs_deployed_live | pass | Live URL checks returned HTTP 200 for `/guide/release-notes-v4.4.0`, `/guide/whats-new-v4.4.0`, `/ja/guide/release-notes-v4.4.0`, `/ja/guide/whats-new-v4.4.0`, and `/brand/harina-hero-v4.4.0.svg`; Docs run `23431498113` passed |
| tag_local_remote | pass | Local tag `v4.4.0` exists and `git ls-remote --tags origin v4.4.0` returned `1822c4f98849738632806c788ab8f15ef068f9df refs/tags/v4.4.0` |
| github_release_verified | pass | `gh release view v4.4.0 --json url,name,body,publishedAt,targetCommitish` confirmed the live release URL, published body, timestamp `2026-03-23T09:58:34Z`, and target commit `3a718bbd5d43f2c748e7485a1ad15a8f9a787994` |
| validation_commands_recorded | pass | Validation commands are listed in Release Context and include local tests, docs build, SVG validation, Actions checks, release verification, and live URL checks |
| publish_date_verified | pass | Published timestamp comes from `gh release view v4.4.0 --json publishedAt` and matches the live release page metadata |

## Notes

- blockers: none
- waivers: none
- follow-up docs tasks: optional discoverability improvement for adding direct `What's New v4.4.0` home/nav shortcuts in docs
