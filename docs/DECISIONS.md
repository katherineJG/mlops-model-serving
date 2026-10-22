# Decisions

1. **Artifact copied into this repo** (`models/churn-v1/`) with a `manifest.json` holding model id/version, library versions, feature schema, threshold and SHA-256. The repo stays independently runnable and the loader can verify existence, compatibility and schema agreement. It is a 6 KB synthetic-data model, so committing it is safe.
2. **joblib is pickle.** Loading executes code. The loader verifies the manifest SHA-256 before `joblib.load`, and the artifact directory is treated as trusted input only. Safer alternative: re-export with skops from Project 01. Deferred; listed as a known limitation.
3. **No MLflow client.** Optional in the spec and not justified for a local artifact.
4. **`prometheus-client` for metrics.** The spec requires operational visibility; labels are bounded (route template, method, status class). Request IDs are never labels.
5. **Pins.** Python 3.12; scikit-learn 1.9.1 and joblib 1.6.0 match Project 01's lockfile, which wrote the artifact. Locust sits in a separate `load` group for load testing.
6. **Base image pinned by digest, uv 0.13.1 pinned.** `python:3.12-slim@sha256:cb33f7f7...`. Bumping is a deliberate edit, so builds do not drift. Action versions in workflows use major tags (`@v4`/`@v5`), not commit SHAs, because SHAs could not be looked up offline; pinning them is a follow-up.
7. **Single Uvicorn worker, model baked into the image.** Simplest correct setup. Rollback is by image tag, documented in the runbook. Container hardening (read-only root, no capabilities) is applied in compose and the container tests, not in the Dockerfile, because those are run-time flags.
8. **Release workflow is manual only** (`workflow_dispatch`), uses a `release` environment (add required reviewers in repo settings), reruns tests, then pushes to GHCR. It has never run.
