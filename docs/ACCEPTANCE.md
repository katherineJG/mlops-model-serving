# Acceptance criteria

Status is `PASS`, `FAIL` or `NOT VERIFIED`, with evidence. Nothing is marked PASS until it has been run.

| Criterion | Status | Evidence |
|---|---|---|
| Valid prediction requests return documented responses | PASS | `tests/contract/test_endpoints.py::test_predict_single_and_batch`; `tests/integration/test_service.py::test_over_a_real_socket`; manual curl against uvicorn returned 200 with 0.943 for the example row |
| Invalid requests return correct 4xx responses | PASS | contract tests: 7 invalid-payload cases, malformed JSON, 404, 405, 413 (declared and chunked), configured batch limit |
| Internal exceptions do not leak sensitive details | PASS (one injected failure path) | `test_unhandled_exception_does_not_leak` injects a RuntimeError containing a fake secret and path; response has neither. Other unhandled-error sources are not separately tested. |
| Model is loaded once and readiness reflects model availability | PASS | `test_model_is_loaded_once_not_per_request` (5 requests, 1 load); `test_readiness_transitions_with_artifact_state`; degraded-app contract tests |
| Version endpoint identifies the loaded model | PASS | `test_version`, `test_degraded_service_is_alive_but_not_ready` |
| Container runs as non-root | NOT VERIFIED | |
| HTTP integration tests run in CI | NOT VERIFIED | |
| Image builds successfully in the documented environment | NOT VERIFIED | |
| Logs and metrics avoid sensitive values and unbounded labels | PASS (limited scope) | tests assert a request ID and a payload value never appear in metrics or log messages, and unknown paths collapse to `route="unmatched"`. Log output was inspected once manually. Not a full audit. |
| README has curl examples, configuration, health semantics, troubleshooting | NOT VERIFIED | |
| Rollback procedure documented and tested, or marked not verified | NOT VERIFIED | |
