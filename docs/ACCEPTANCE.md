# Acceptance criteria

Status is `PASS`, `FAIL` or `NOT VERIFIED`, with evidence. Nothing is marked PASS until it has been run.

| Criterion | Status | Evidence |
|---|---|---|
| Valid prediction requests return documented responses | PASS | `tests/contract/test_endpoints.py::test_predict_single_and_batch`; `tests/integration/test_service.py::test_over_a_real_socket`; manual curl against uvicorn returned 200 with 0.943 for the example row |
| Invalid requests return correct 4xx responses | PASS | contract tests: 7 invalid-payload cases, malformed JSON, 404, 405, 413 (declared and chunked), configured batch limit |
| Internal exceptions do not leak sensitive details | PASS (one injected failure path) | `test_unhandled_exception_does_not_leak` injects a RuntimeError containing a fake secret and path; response has neither. Other unhandled-error sources are not separately tested. |
| Model is loaded once and readiness reflects model availability | PASS | `test_model_is_loaded_once_not_per_request` (5 requests, 1 load); `test_readiness_transitions_with_artifact_state`; degraded-app contract tests |
| Version endpoint identifies the loaded model | PASS | `test_version`, `test_degraded_service_is_alive_but_not_ready` |
| Container runs as non-root | PASS (local) | `test_runs_as_non_root` against the built image: `id -u` is 10001, image `USER` is 10001; also ran with `--read-only --cap-drop ALL --no-new-privileges`. Also passed in the CI run. |
| HTTP integration tests run in CI | PASS | GitHub Actions CI run on `main` (2026-10-26): `checks` job ran ruff, ruff format, mypy and 60 tests (5 container tests skipped there); `image` job built the image and ran the 5 container tests against it, all passed. |
| Image builds successfully in the documented environment | PASS (local only) | `docker build` succeeded with Docker 29.8.2 on Windows 11 (Linux engine), base `python:3.12-slim` pinned by digest. CI build also succeeded (`ubuntu-24.04` runner). |
| Logs and metrics avoid sensitive values and unbounded labels | PASS (limited scope) | tests assert a request ID and a payload value never appear in metrics or log messages, and unknown paths collapse to `route="unmatched"`. Log output was inspected once manually. Not a full audit. |
| README has curl examples, configuration, health semantics, troubleshooting | PASS (content present) | All four sections exist; the example responses were captured from a running container. A from-scratch walkthrough by a new contributor has not been done. |
| Rollback procedure documented and tested, or marked not verified | PASS (local, limited) | `docs/RUNBOOK.md`: rollback from a deliberately bad image back to the previous tag, observed with `docker run` on one host. Not tested by pulling the previous tag from a registry, through Compose or under live traffic. |
