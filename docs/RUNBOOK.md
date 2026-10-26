# Runbook

Operating notes for `mlops-model-serving`. Anything not marked verified has not been run.

## Run

```bash
docker build -t mlops-model-serving:local --build-arg SOURCE_REVISION=$(git rev-parse --short HEAD) .
docker run -d --name mss -p 127.0.0.1:8000:8000 --read-only --cap-drop ALL \
  --security-opt no-new-privileges mlops-model-serving:local
curl -s localhost:8000/health/ready     # {"status":"ready"} once the model is verified
```

Or `docker compose -f deployment/docker-compose.yml up --build`.

## Health semantics

| Probe | Meaning | Use it for |
|---|---|---|
| `GET /health/live` | The process answers. Ignores the model. | Restart decisions |
| `GET /health/ready` | A verified model is loaded. 503 otherwise. | Routing traffic; the image's Docker `HEALTHCHECK` uses this one |

A container whose model failed to load stays up, reports **live 200, ready 503**, and Docker marks it `unhealthy`. `/predict` returns 503 with `Retry-After: 5`.

## Release

1. Merge to `main` with green CI (CI has not run on GitHub yet; see `ACCEPTANCE.md`).
2. Run the **Release image** workflow manually from `main`, typing the version (for example `0.1.1`) in both the version and confirm fields. A `guard` job stops the run unless: it is on `main`, the person starting it is the repository owner, the version is `MAJOR.MINOR.PATCH`, the confirmation matches, and the exact commit has a successful CI run. Then it reruns tests, builds, runs the container tests against that exact image, and pushes `ghcr.io/<owner>/<repo>:<version>`. **Verified once** on 2026-10-26 with a throwaway version, `0.0.1` (the same run was done in an earlier copy of this repository before it was recreated): the guard passed, including its CI lookup, every publish step passed, the image pulled back from GHCR ran as non-root and `/version` reported the build commit as `source_revision`, and the throwaway package was deleted afterwards. A run with a mismatched confirmation stopped at `guard` and skipped `publish`. The guard's other rejections (non-owner, non-`main` ref, version format, commit without CI) were checked locally only.
3. Deploy by pulling that exact tag. Never deploy `latest`; there is no `latest` tag.
4. Check `GET /version` reports the expected `model_id`, `model_version` and `source_revision`, and `/health/ready` is 200.
5. Keep the previous tag available; it is the rollback target.

Model changes ship as a new image. There is no in-place reload and no admin endpoint, by design.

## Rollback

**Procedure** (single host, plain Docker):

```bash
docker rm -f mss
docker run -d --name mss -p 127.0.0.1:8000:8000 --read-only --cap-drop ALL \
  --security-opt no-new-privileges mlops-model-serving:<previous-tag>
curl -s localhost:8000/health/ready && curl -s localhost:8000/version
```

**Verified locally** (2026-10-22, Docker 29.8.2): with `0.1.0` serving, I "released" `0.2.0-bad` (same code, model file corrupted after the manifest checksum was recorded) and observed:

| Step | live | ready | predict | `/version` model |
|---|---|---|---|---|
| `0.1.0` running | 200 | 200 | 200 | `churn-v1` / `1` |
| deploy `0.2.0-bad` | 200 | **503** | **503** | `null` (log: `reason: checksum_mismatch`) |
| rollback to `0.1.0` | 200 | 200 | 200 | `churn-v1` / `1` |

Not verified: rollback by pulling a previous tag from a registry, through Compose, or under live traffic. Rollback here means a short interruption while the container is replaced; there is no zero-downtime or canary mechanism (Project 05).

## Troubleshooting by symptom

| Symptom | Likely cause | Check |
|---|---|---|
| ready 503, `/predict` 503 | Model failed verification at startup | `docker logs <c> \| grep "model load failed"` and read `reason` |
| Container exits at start | Invalid environment value | Logs show `ConfigError` text, e.g. `MAX_BATCH_SIZE must be an integer` |
| 422 on a valid-looking request | A field is out of the documented range/category set, or an unknown field was sent | `error.details[].field` names the path; see `API_CONTRACT.md` |
| 413 | Body over 256 KiB | Split the batch (max 100 instances) |
| Latency rises with concurrency, throughput flat | One worker is saturated (~185 req/s on the test machine) | Add replicas or `--workers`; see `LOAD_TEST.md` |

Model load failure reasons (`reason` in logs only, never in responses): `manifest_missing`, `manifest_invalid`, `artifact_missing`, `checksum_mismatch`, `version_mismatch`, `artifact_unreadable`, `artifact_incompatible`, `schema_mismatch`, `smoke_test_failed`.

Correlate a caller's report with logs using the `request_id` from the error body or `X-Request-ID` header.

## Security notes

- No authentication; bind to loopback or an internal network, or put a gateway in front.
- `/metrics` is unauthenticated and exposes route-level counts only.
- The model file is a pickle. The checksum catches corruption and accidental swaps, not an attacker who can write both the file and its manifest. Keep the model path write-protected.
- Logs contain request ID, route template, status, latency, model version and batch size. No payloads.
- No secrets are required or baked into the image. `SOURCE_REVISION` is a plain build argument.

## Known limitations

- Trained on synthetic data; predictions have no real-world validity.
- Single worker by default, about 185 req/s on the test machine under the test workload only.
- No TLS, auth, rate limiting, tracing, or drift monitoring (Project 03).
- GitHub Actions versions use major tags (`@v4`, `@v5`), not commit SHAs.
- Releases have no separate approval step (see `DECISIONS.md`); starting the run is the approval.
- `make` targets were not run on the development machine (no `make` installed); the underlying commands were.
