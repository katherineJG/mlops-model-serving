# Acceptance criteria

Status is `PASS`, `FAIL` or `NOT VERIFIED`, with evidence. Nothing is marked PASS until it has been run.

| Criterion | Status | Evidence |
|---|---|---|
| Valid prediction requests return documented responses | NOT VERIFIED | |
| Invalid requests return correct 4xx responses | NOT VERIFIED | |
| Internal exceptions do not leak sensitive details | NOT VERIFIED | |
| Model is loaded once and readiness reflects model availability | NOT VERIFIED | |
| Version endpoint identifies the loaded model | NOT VERIFIED | |
| Container runs as non-root | NOT VERIFIED | |
| HTTP integration tests run in CI | NOT VERIFIED | |
| Image builds successfully in the documented environment | NOT VERIFIED | |
| Logs and metrics avoid sensitive values and unbounded labels | NOT VERIFIED | |
| README has curl examples, configuration, health semantics, troubleshooting | NOT VERIFIED | |
| Rollback procedure documented and tested, or marked not verified | NOT VERIFIED | |
