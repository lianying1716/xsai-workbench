# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Shape

This is a **workbench of independent projects**, not a single application. There is no root Git repository and no shared build. Each subdirectory has its own toolchain, lockfile, and conventions. Commit inside the affected subproject only, and avoid cross-project refactors unless coordinated.

Always `cd` into the owning project before running any command. The projects are unrelated except that several deal with downloading/syncing media from Chinese platforms (Bilibili, Douyin, Xiaohongshu, WeChat).

### Branching

**`main` is the one and only mainline.** All other branches (`feat/*`, `fix/*`, `docs/*`, `chore/*`, etc.) are temporary. Once a temporary branch passes the user-visible acceptance check, merge it back into `main` and delete it, so `main` stays the single continuously deliverable mainline. Do not sit on a temporary branch long-term; everything on `main` should already be accepted.

### Releasing (hard rule)

**Never publish a new version without the user's explicit confirmation.** By default, only develop, commit, and verify. Publishing pushes an update to every user (they see an update prompt and may one-click upgrade), so it is a user-authorized action, not a wrap-up step.

"Publishing a new version" means any of: pushing a version tag (`git tag vX.Y.Z` + `git push origin <tag>`, which triggers `.github/workflows/release.yml` to build and push images to GHCR); creating/updating a GitHub Release (`gh release create` — this is the App's "check for updates" source); pushing/overwriting a versioned image tag or switching a deployment's `PLATFORM_VERSION`; or triggering an upgrade on a production/self-hosted instance (including the updater `/upgrade` endpoint).

1. **Ask first.** When the work reaches a "ready to release" state, stop and confirm the version number and whether to release; if the user hasn't confirmed, stay at commit/local verification and do not tag or push.
2. **The user sets the version number.** Do not bump it on your own; do not guess unless told.
3. **Committing is not releasing.** Committing on a temporary branch or merging into `main` is not a release by itself; only the actions above are.
4. Release only when the user explicitly says "release / publish / cut a new version", then report the version, image, and Release link.

### Every release must be updated + verified on the NAS (hard rule)

**After publishing any new version, update and verify it on the owner's fnOS NAS — both steps, no exceptions.** Publishing is not the finish line; a version that hasn't been run and verified on the NAS is not done.

Standard steps (SSH host `fnos` / `192.168.2.4`; deploy dir `/vol1/1000/docker/platform-api/src`):

1. **Update** to the new version: `PLATFORM_VERSION=<ver> docker compose --profile updater pull` then `PLATFORM_VERSION=<ver> docker compose --profile updater up -d`; or use the web "版本与升级 → 检查更新 → 升级到 <ver>" flow. Confirm `/api/system/version` reports the new `app_version`, `db_in_sync=true`, and `.env`'s `PLATFORM_VERSION` is pinned.
2. **Verify this change** on the NAS with a real acceptance run (real endpoints / real data / real browser events) and keep command output or screenshots as evidence — "it starts" is not enough.
3. **Regress**: confirm existing functionality still works (key endpoints, worker, version guard).
4. Report the result honestly; if something can't be verified (e.g. no admin password), say exactly which step is unverified.

> Rationale: the NAS is the reference self-hosted deployment holding the user's real data. Pushing CI/images without running on the NAS means it was never verified — past regressions (the upgrade `pin` EBUSY, storage-browse availability) were only caught on the NAS.

## Projects at a Glance

| Dir | Stack | Purpose |
|-----|-------|---------|
| `bili-sync/` | Rust workspace + Svelte | Sync Bilibili favorites/collections to local media |
| `dysync.net/` | .NET 6 + Vue 3 | Sync Douyin favorites/likes to Emby/Jellyfin ("抖小云") |
| `MediaCrawler/` | Python (uv) + Playwright | Multi-platform social scraper (xhs/dy/ks/bili/wb/tieba/zhihu) |
| `wechat-article-exporter/` | Nuxt 3 SPA | Batch-export WeChat public-account articles |
| `faster-whisper/` | Python (setup.py) | Whisper transcription on CTranslate2 |
| `yt-dlp/` | Python (hatchling) | CLI media downloader (youtube-dl fork) |

## Per-Project Commands & Architecture

### bili-sync (Rust + Svelte)
Tasks run through `Justfile` at the project root; frontend uses **bun**, Rust targets `x86_64-unknown-linux-musl`, toolchain pinned to **1.96.0** (edition 2024).
- `just debug` — build frontend then `cargo run` (main dev loop)
- `just build` — release build (builds frontend first); `just build-docker` for image
- `cargo test` — backend tests; single: `cargo test -p bili_sync <module>::<test_name>`
- `cd web && bun run check && bun run lint` — Svelte check + prettier/eslint; `bun run dev` for vite
- Lint/format: `cargo clippy`, `cargo fmt` (rustfmt: `max_width=120`, `imports_granularity=Module`, `group_imports=StdExternalCrate`)

Crates in `crates/`: `bili_sync` (main binary, default member) holds modules `api` (axum routes), `bilibili` (B站 client), `adapter` (favorite/collection/submission/watch_later sources), `downloader`, `workflow`, `task`, `config`, `database`; `bili_sync_entity` (sea-orm entities); `bili_sync_migration` (sea-orm migrations). The **Svelte frontend is embedded into the binary** via `rust-embed-for-web` (`web/build` folder) and served by axum with SPA fallback under `/api` (auth via `Authorization` header token; WebSocket for live logs). DB is SQLite via sea-orm at `CONFIG_DIR/data.sqlite`; migrations run on startup and **reject upgrades from versions <2.6.0**. Config is versioned and stored in the DB (`VersionedConfig`). Requires `ffmpeg` on PATH.

### dysync.net (.NET 6 + Vue 3)
Single-project solution `dy.net.sln`; embedded Vue admin SPA in `app/`.
- `dotnet build dy.net.sln`; `dotnet run --project dy.net.csproj` (optional arg[0] = DB base path)
- Backend listens on `http://*:10101` (hardcoded in `Program.cs`, overrides launchSettings)
- `cd app && yarn dev` (Vite port 8001) / `yarn build` (`vue-tsc --noEmit && vite build` → `app/dist`)
- **No tests exist.** Backend uses **yarn** for the UI (a stray `pnpm-lock.yaml` also exists; prefer yarn).

Layering: `Controllers/` → `service/` (Douyin* + AdminUserService) → `repository/` (BaseRepository) → `model/` (`entity`/`dto`/`response`). DI auto-registers anything in `dy.net.repository`/`dy.net.service` via `ServiceLifetimeAttribute` (`extension/ServiceExtension.cs`). ORM is **SqlSugar** with SQLite, **Code-First auto-creates tables on startup** (no migration commands). Sync jobs in `job/` run on **Quartz** with a persistent SQLite store (`QRTZ_` tables). Auth is JWT Bearer; logging via Serilog. A closed-source `lib/dy.sync.lib.dll` is referenced. `appsettings.json` is git-ignored. Default admin seed: `douyin` / `douyin2026`. Prod serves `app/dist` as SPA static files (non-Development only), all on port 10101.

### MediaCrawler (Python + Playwright)
Dependency manager is **uv**; Python ≥3.11.
- `uv sync && uv run playwright install` — setup
- `uv run main.py --platform xhs --lt qrcode --type search` — run (platforms xhs/dy/ks/bili/wb/tieba/zhihu; `--type` search|detail|creator; `--lt` qrcode|phone|cookie)
- `uv run main.py --init_db sqlite` — init DB (or mysql|postgres)
- `uv run uvicorn api.main:app --port 8080 --reload` — WebUI
- `uv run pytest` — tests; single: `uv run pytest tests/test_store_factory.py::test_name` (note **two** test dirs: `tests/` and `test/`)
- `pre-commit run --all-files`; type check `mypy`

`main.py` → `CrawlerFactory` maps platform code to a crawler in `media_platform/<platform>/` (each implements `base/base_crawler.py:AbstractCrawler`). Uses Playwright (CDP mode on by default against local Chrome, port 9222) to keep login state and obtain signatures via JS — no JS reverse engineering. Output is pluggable via `store/` factory (csv/json/db/mongo); `cache/` and `proxy/` also use factory patterns. Config lives in the `config/` package (`base_config.py` + per-platform); **CLI flags override config at runtime**. **Every `.py` file requires a copyright header** (enforced by pre-commit via `tools/file_header_manager.py`). Research/learning use only.

### wechat-article-exporter (Nuxt 3)
**Has its own detailed CLAUDE.md — read it.** Package manager **yarn 1.22**, Node ≥22.
- `yarn dev` (or `yarn debug` for `--inspect`); `yarn build` → `.output/`
- `yarn format` → `biome check --write` (**Biome linter is disabled**, formatting only)
- **No test framework.** `test/*.ts` are standalone scripts run via `npx tsx test/<name>.ts` (use the `#shared/` alias, run in Nuxt context).

Client-side SPA (`ssr: false`). Data flow: `apis/index.ts` → Nitro proxy endpoints in `server/api/` (handle CORS/cookie forwarding) → WeChat MP. Articles cached in IndexedDB via Dexie (`store/v2/`). Downloads via `utils/download/Downloader.ts` + `Exporter.ts` (Cheerio/Turndown/ExcelJS/JSZip). WeChat QR login under `server/api/web/login/`; PDF via puppeteer. AG Grid Enterprise needs `NUXT_AGGRID_LICENSE`.

### faster-whisper (Python)
Classic `setup.py`; Python ≥3.9; version in `faster_whisper/version.py`.
- `pip install -e .[dev]` — dev install
- `pytest tests/`; single: `pytest tests/test_transcribe.py::test_transcribe`
- `black .`, `isort .` (profile=black), `flake8 .` (max-line 100, ignore E203/W503)

Wraps OpenAI Whisper on the **CTranslate2** inference engine (int8/fp16 quantization). Entry point is `transcribe.py` (`WhisperModel` API); supporting modules `audio.py`, `feature_extractor.py`, `tokenizer.py`, `vad.py`. Fixtures in `tests/data/`.

### yt-dlp (Python)
Modern build: **hatchling** backend, **ruff** linting, **uv** installer; Python ≥3.10.
- `make test` or `python -m pytest -Werror`; offline only: `make offlinetest` (`-m "not download"`)
- Single: `python -m pytest test/test_jsinterp.py::TestJSInterpreter::test_basic` (tests in `test/`, singular)
- `make codetest` → `ruff check .` + `autopep8 --diff .`; `make lazy-extractors` regenerates the extractor index

Orchestrator `YoutubeDL.py`, CLI `options.py`; subpackages `extractor/` (site extractors + generated `lazy_extractors.py`), `postprocessor/`, `downloader/`, `networking/`. Ruff: line-length 120, single inline quotes; many stdlib `import-from`s and deprecated `compat`/`utils` helpers are banned-api.

## Conventions
- Do not commit cookies, tokens, local databases, generated media, logs, or `.env` files.
- Keep each lockfile with its project. Follow the local formatter/linter for each subproject.
- bili-sync favors Conventional Commits (`feat:`, `fix:`, `perf:`, `chore:`); other projects use concise summaries.
- Code comments in dysync.net and MediaCrawler are largely in Chinese.
