# Refactor & Integration Plan

## Objectives
- Merge the functionality from `ipt-qbit-integration` into `main` while resolving divergence cleanly.
- Remove dead code, unused assets, and duplicate configuration to keep the tree minimal.
- Improve runtime efficiency (faster scans, lighter memory footprint), and tighten code quality (typing, linting, tests).

## Current Status
- ✅ `ipt-qbit-integration` merged into `main` (b90069d) with download approvals aligned to the Flask API.
- ✅ New integrations package (`integrations/`, `metadata_service.py`), docs, and pytest coverage shipped in PR #8.
- 🔄 Next focus: stabilize post-merge, prune leftovers, and ensure Docker/CI parity ahead of release.

## Completed Workstreams
- Baseline audit and service inventory captured during the integration effort; current entrypoints are documented in `README.md` and `IPT_QBIT_INTEGRATION.md`.
- Branch diff analysis resolved through the PR staging merge; all conflicts and duplicate logic collapsed into unified modules.
- Integration interface consolidated: IPT ↔ qBit logic, shared helpers, and configuration now live under `integrations/` via `DownloadManager`, qBittorrent client, Radarr bridge, and Telegram handler.

## Upcoming Workstreams

### 1. Cleanup & Pruning
- Build a list of unused files via `rg --files` + manual review; confirm with maintainers before deleting.
- Drop stale docs (superseded Markdown), unused scripts, redundant templates/static assets.
- Remove dead code paths flagged by coverage reports, and tighten type hints to make reachability obvious.

### 2. Performance Improvements
- Profile critical workflows (scanner loop, metadata fetchers, job scheduling) using `cProfile`/logging timers.
- Add batching/caching where beneficial (reuse HTTP sessions, cache metadata lookups, minimize filesystem hits).
- Ensure DB/file handles are closed promptly; review async/parallelism opportunities if I/O-bound.

### 3. Docker Parity
- Update the primary `Dockerfile` to mirror the refactored entrypoints and dependencies; remove layer duplication and ensure builds stay reproducible.
- Refresh `docker-compose.yml` (and related overrides) so local, CI, and production stacks stay in sync; document required env vars and secrets.
- Add a `make`/script target that runs the full service inside containers end-to-end, including volume mounts and seeding steps.
- Harden healthchecks/readiness probes for each service; validate that logs, cache directories, and persistent volumes land in the expected paths.
- Capture docs for common Docker workflows (build, test, debug) and bake smoke tests into CI to catch regressions in container startup.

### 4. Testing & Quality Gates
- Run the expanded pytest suite on `main` to capture the new baseline and compare against pre-merge results.
- Align unit/integration tests between branches; merge test suites and remove duplicates.
- Expand coverage for refactored modules (especially around IPT/qBit interactions and file deletion logic).
- **Cookie-auth regression suite:** Build a dedicated pytest module that parameterizes real-world cookie/header permutations, deliberately expired cookies, and throttled responses; assert that retries back off correctly, tokens rotate, and that the adapter never mutates shared state between runs.
- **Negative-path resilience tests:** Simulate IPT returning captchas, maintenance banners, HTTP 40x/50x, or malformed JSON to verify the integration fails fast, logs actionable errors, and never attempts to reuse poisoned sessions.
- **IPT/qBit contract tests:** Record golden HTTP interactions (using `pytest-recording`/VCR.py) for the full handshake, torrent add/remove flows, and metadata pulls; lock the schema and response shapes so future refactors raise alarms when upstream contracts drift.
- **Concurrency and race-condition tests:** Use `pytest` with `asyncio` or thread pools to trigger simultaneous scans/download orchestration; assert that cookie refresh, queue management, and disk writes remain deterministic under parallel load.
- **Long-haul smoke tests:** Run extended soak tests (e.g., 12-hour cron simulation) inside Docker Compose to observe memory usage, cookie churn, and qBit queue depth; flag regressions in metrics or log noise.
- **Load/performance scenarios:** Replay high-volume IPT payloads and torrent lists to benchmark throughput, using profiling hooks to capture per-request latency and identify hotspots introduced during refactor.
- Introduce lint/type checks (`ruff`, `mypy`) and wire into CI (GitHub Actions or existing pipeline).

### 5. Deployment & Verification
- Update Docker/compose definitions to reflect new module layout; prune unused services.
- Regenerate or validate configuration docs (`README.md`, `IPT_QBIT_INTEGRATION.md`) to match merged behavior.
- Perform end-to-end dry run: run scanners, ingest data, verify outputs/logs, and ensure integrations still function.
- Tag release candidate, capture changelog, and communicate breaking changes to stakeholders.

## Execution Notes
- Tackle cleanup, performance, and Docker parity in incremental PRs to keep reviewable and reduce regression risk.
- Keep a checklist of removed files/modules to confirm no runtime dependency remains.
- After completion, enforce branch protection to prevent reintroducing divergent copies of the integration logic.
