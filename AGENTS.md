# Repository Guidelines

## Repository Shape

This root is a **workbench of independent projects**, not a single application. There is **no root
Git repository and no shared build**. Each subdirectory has its own toolchain, lockfile, and
conventions. Always `cd` into the owning project before running any command. Commit inside the
affected subproject only, and avoid cross-project refactors unless coordinated.

`platform-api/` (with `docs/`) is a *new* unified platform being built on top of the older projects;
the older projects remain independent upstreams and are **not** to be refactored to serve it —
their code is read and adapted (with source attribution), not rewritten.

### Branching（分支约定）

**`main` 是唯一主线**；其余分支（如 `feat/*`、`fix/*`、`docs/*`、`chore/*`）一律视为临时分支。
临时分支做完并经用户可见验收后，**合回 `main`** 并在合并后删除，保持 `main` 是持续可交付的单一主线。
不要长期停留在临时分支上；`main` 上的历史应当始终是「已验收」的状态。

## Project Structure & Module Organization

| Dir | Stack | Purpose |
|-----|-------|---------|
| `platform-api/` | Python 3.11+ (FastAPI) + Vue 3 | **Unified material-collection platform**: account center, sync, transcription, crawl, AI access |
| `docs/` | Markdown | Design docs & master plan for `platform-api` (see Document Map below) |
| `bili-sync/` | Rust workspace + Svelte | Sync Bilibili favorites/collections to local media |
| `dysync.net/` | ASP.NET Core (.NET 6) + Vue 3 | Sync Douyin favorites/likes to Emby/Jellyfin ("抖小云") |
| `MediaCrawler/` | Python (uv) + Playwright | Multi-platform social scraper (xhs/dy/ks/bili/wb/tieba/zhihu) |
| `wechat-article-exporter/` | Nuxt 3 SPA | Batch-export WeChat public-account articles |
| `faster-whisper/` | Python (setup.py) | Whisper transcription on CTranslate2 |
| `yt-dlp/` | Python (hatchling) | CLI media downloader (youtube-dl fork) |

Each of `bili-sync`, `dysync.net`, `faster-whisper`, `MediaCrawler`, `wechat-article-exporter`, and
`yt-dlp` is its own Git repo. `platform-api/` and `docs/` are **not** git repos yet.
`wechat-article-exporter/` has its own detailed `CLAUDE.md` — read it before working there.

## Document Map (`docs/`)

`platform-api` development is driven by these docs; when in doubt follow this priority:
`development-master-plan.md` > `workbench-requirements-and-design-v1.md` >
`unified-account-center-design.md` > `unified-content-platform-prd.md` +
`backend-module-final-review.md` > `backend-module-architecture-*.md`.

- `development-master-plan.md` — the master plan: phases P0–P6, directory layout, task checklist.
- `workbench-requirements-and-design-v1.md` — full requirements & design, API list, phasing.
- `unified-account-center-design.md` — account-center (P1) detailed design.
- `unified-content-platform-prd.md` / `backend-module-final-review.md` — locked architecture decisions.
- `backend-module-architecture-*.md` — per-upstream capability/login details (read when writing adapters).
- `license-and-usage-compliance.md` — source licenses & attribution (MediaCrawler is non-commercial, authorized).
- `plans/` — phasing history (design + plan pairs per feature); see `plans/README.md` for the index.
  `plans/evidence/` holds acceptance screenshots/scripts (one-off, not reusable tooling).

Note: the upstream capability docs (`backend-module-architecture-*.md`) describe what each **upstream**
project can do, not what `platform-api` currently integrates. `platform-api` currently ships **5 crawl
platforms: bilibili / douyin / xhs / kuaishou / zhihu** (weibo + tieba were removed 2026-10-08).

### Architecture Red Lines (do not change unilaterally)

1. Backend = **FastAPI**; DB = **PostgreSQL** (SQLite allowed for local dev, schema-compatible); deploy = **Docker Compose**.
2. **Single-admin** mode — no multi-user / roles.
3. **All credentials AES-GCM encrypted at rest**; key from env/keyfile, never in DB or git; API/frontend responses are **always redacted** — plaintext credentials only go in, never out.
4. **API is the product**: frontend, MCP server, and external HTTP clients all use the same `/api/*`. Auth is two-track: admin session token (frontend) + API Key with scope & rate limit (AI/external). No "web-only" operations.
5. Task queue is a **PostgreSQL table** (`SELECT ... FOR UPDATE SKIP LOCKED`) — **no Redis/Celery**.
6. **One API process + one worker process**: API does light work only; download/transcribe/analyze go to the worker.
7. File paths are always `storage_root + relative_path`; external APIs must not accept absolute output paths.
8. Store metric snapshots (`content_metric_snapshot`) from day one.
9. **Banned**: wechat-exporter `_debug` plaintext export & plaintext KV; dysync default password `douyin/douyin2026`; yt-dlp plugins/self-update/ExecPP/file URLs/arbitrary external args; exposing faster-whisper's Python API directly (must go through queue+worker).

## Build, Test, and Development Commands

Run commands inside the owning project.

### platform-api

```bash
cd platform-api
uv sync --extra postgres --extra dev          # deps (Python >= 3.11); + --extra browser for Playwright
uv run uvicorn app.main:app --port 9100       # backend, auto-creates tables on first start
uv run pytest tests/ -q                        # tests
python -m app.workers.runner                   # worker process (PG job queue consumer)
./dev.sh [sync|serve|worker|preview|web]       # local helper (see dev/prod isolation below)
cd web && npm install && npm run dev           # Vite dev server :5173 (proxy /api -> :9100)
cd web && npm run build                        # compile check only; output -> web/dist (NOT app/static)
./dev.sh web                                   # RELEASE build into app/static (needs confirmation)
./dev.sh preview                               # serve the built release locally (app/static)
```

**Dev / release isolation (hard rule):** `platform-api` is being developed, so the
backend does NOT host the frontend unless `PLATFORM_SERVE_FRONTEND=true` (release/Docker).
Development uses the Vite dev server on `:5173`; the backend only serves `/api`.
Do NOT run the release build (`./dev.sh web`, `npm run build:release`) unless the user
explicitly confirms a release package is wanted.

Dev DB convenience (local PG on 5433 to match prod shape):

```bash
docker run -d --name platform-pg-dev \
  -e POSTGRES_USER=platform -e POSTGRES_PASSWORD=platform -e POSTGRES_DB=platform \
  -p 5433:5432 -v platform-pg-dev-data:/var/lib/postgresql/data postgres:17-alpine
```

Config uses the `PLATFORM_` env prefix (e.g. `PLATFORM_PORT`, `PLATFORM_DATABASE_URL`,
`PLATFORM_CREDENTIAL_ENC_KEY`). Credential-key priority: env var > key file > `data/secret.key`
(dev fallback, auto-generated). **The key is not in git; losing it invalidates all credentials.**

### Other projects

- `cd bili-sync && just debug` (build frontend + run Rust); `just build` (prod). `cd bili-sync/web && bun run check && bun run lint`; `cargo test`, `cargo clippy`, `cargo fmt`.
- `cd dysync.net && dotnet build dy.net.sln`; `dotnet run --project dy.net.csproj` (port 10101); `cd app && yarn dev` (Vite :8001) / `yarn build`. No tests.
- `cd wechat-article-exporter && yarn dev`; `yarn build && yarn format`. No test framework (`test/*.ts` run via `npx tsx test/<name>.ts`).
- `cd faster-whisper && python -m pytest tests`; format `black .` + `isort .`, lint `flake8 .`.
- `cd MediaCrawler && uv sync && uv run playwright install`; `uv run pytest` (note two dirs: `tests/` and `test/`); `pre-commit run --all-files`; types `mypy`.
- `cd yt-dlp && make test` (or `python -m pytest -Werror`); offline `make offlinetest`; lint `make codetest`.

## Coding Style & Naming Conventions

Follow the local formatter for each project.

- **platform-api**: Python 3.11+, FastAPI + SQLAlchemy 2.0. `snake_case` functions/modules, `PascalCase` ORM/Pydantic classes. Keep route handlers thin; business logic in `app/services/`, platform adapters in `app/modules/`, shared primitives in `app/core/`. Comments/docstrings in Chinese are fine (matches existing code).
- **Rust** (`bili-sync`): `rustfmt.toml`, `cargo fmt`; `snake_case`; line width 120.
- **Python** (others): Black-compatible formatting, Black-profile `isort`, 100-char lines where configured.
- **Nuxt/Vue/Svelte**: TypeScript with the configured Biome / Prettier / ESLint.
- **C#** (`dysync.net`): `PascalCase` types, `camelCase` locals; comments largely in Chinese.
- `MediaCrawler`: every `.py` file requires a copyright header (enforced by pre-commit).

## Testing Guidelines

Add tests next to the suite of the project you change. Use `test_*.py` for Python.

- `platform-api`: `uv run pytest tests/ -q`; tests live in `tests/` (e.g. `test_crypto.py`, `test_accounts_api.py`, `test_pipeline_e2e.py`).
- No test script (frontend-only changes): run the build plus formatter/linter.
- Rust backend logic: `cargo test` from `bili-sync/`.
- `yt-dlp` tests live in `test/` (singular); `MediaCrawler` has both `tests/` and `test/`.

## Commit & Pull Request Guidelines

There is no root Git repository; commit inside the affected subproject only.

- `platform-api` and `bili-sync` favor Conventional Commits (`feat:`, `fix:`, `perf:`, `chore:`); other projects use concise summaries.
- One commit per "acceptance-able small feature"; run that phase's user-visible acceptance check + backend tests + frontend `build` before declaring a phase done.

PRs should describe the change, list the commands run, link issues when applicable, and include screenshots for UI changes. Note configuration, database, or migration impacts explicitly (especially credential-key handling).

## Security & Configuration Tips

- Do not commit cookies, tokens, local databases, generated media, logs, or `.env` files.
- Keep each lockfile with its project; avoid cross-project refactors unless coordinated.
- Before any change touching credentials, paths, or external parameters, self-check: credentials encrypted? responses redacted? paths via `storage_root`? external APIs rejecting absolute paths/arbitrary args?
- Upstream code in the older projects is **adapted with source attribution** (bili-sync/dysync.net/wechat-article-exporter = MIT; MediaCrawler = non-commercial learning license, authorized — see `docs/license-and-usage-compliance.md`).

## Windows Real-Device Acceptance & Debugging

**Trigger**: a task requires running a GUI app on Windows and needs *real behavior + all errors* —
clicking buttons, filling inputs, running a full flow, reproducing UI bugs, functional acceptance, or
capturing crash scenes (this includes desktop-end acceptance and reproducing user-reported UI issues).

**Use**: the `windows-desktop-driving` skill (scripts in its `scripts/`: `cdp.mjs` remote control +
error harvesting, `xs-evidence.ps1` system-level evidence, `xs-session.ps1`/`xs-gui.ps1` desktop-level
screenshots & input, `xs-dumps-on.ps1` crash dumps).

**Three prerequisites** (without them you can only guess from screenshots): the remote app has the debug
port open (Xingsuan desktop = machine env var `XINGSUAN_DEV_DEBUG_PORT=62071`); an SSH tunnel exists on
the Linux side (`ssh -N -L 62071:127.0.0.1:62071 win-ztb`); Windows has a **logged-in interactive
desktop session** (auto-login already enabled).

**Iron rules**:
1. Real-device acceptance must use **real events** (CDP `Input` domain real mouse/keyboard) — jsdom/unit tests may not impersonate UI acceptance.
2. Start error harvesting (`cdp.mjs watch`) **before** running the flow; check `cdp.mjs report` at the end — evidence, not repro luck.
3. Conclusions must carry real command output and absolute screenshot paths; if unavailable, write "not verified" — **never fabricate**.
4. Clean up: test scene packages, SSH tunnels, temp files.

**Boundaries**: system-level ops (SSH/SMB/auto-login/encryption/toolchain) → `windows-remote-ops`;
acceptance flow & report spec → `remote-desktop-dev-acceptance`; Xingsuan desktop entry →
`xingsuan-desktop-acceptance`. If these skills aren't in the current agent home, read the same-named
`SKILL.md` under `~/.hermes/skills/`.
