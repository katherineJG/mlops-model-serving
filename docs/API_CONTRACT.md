# API contract

Source of truth for the HTTP interface. `app/schemas.py` implements it; contract tests check it. All bodies are JSON. Every response carries an `X-Request-ID` header.

## Conventions

- **Request ID:** if the caller sends `X-Request-ID` (1–64 chars of `[A-Za-z0-9._-]`) it is reused, otherwise the server generates a UUID4. The ID appears in logs, error bodies and the response header. It is never a metric label.
- **Metrics:** `http_requests_total{method,route,status_class}`, `http_request_duration_seconds{method,route}`, `predict_instances_total`, `model_loaded`. `route` is the route template (`unmatched` for unknown paths) and `method` is limited to standard verbs, so label cardinality is bounded.
- **No authentication.** The API is intended for a trusted network (see the threat notes in `ARCHITECTURE.md`). There are no admin or reload endpoints.
- **Batch limit:** 1 to 100 instances per request. The body limit is 256 KiB; larger bodies get 413.
- **Not exposed to callers:** stack traces, local paths, library versions, secrets, and the value of any invalid input.

## Endpoints

| Method and path | Purpose | Success | Failures |
|---|---|---|---|
| `GET /health/live` | Process is up. Never checks the model. | 200 `{"status": "ok"}` | none expected |
| `GET /health/ready` | Model loaded and verified. | 200 `{"status": "ready"}` | 503 `{"status": "not_ready"}` |
| `GET /version` | App and model identity. | 200 `VersionResponse` | none (model fields are `null` if not loaded) |
| `POST /predict` | Score 1–100 customers. | 200 `PredictResponse` | 413, 422, 503 |

Any other path returns 404 with an error body. A wrong method returns 405 with an error body.

### POST /predict

Request:

```json
{
  "instances": [
    {
      "senior_citizen": 0,
      "tenure_months": 3,
      "monthly_charges": 80.0,
      "total_charges": 240.0,
      "gender": "female",
      "partner": "no",
      "contract": "month-to-month",
      "internet_service": "fiber",
      "payment_method": "electronic-check",
      "paperless_billing": "yes"
    }
  ]
}
```

Field rules (all fields required; unknown fields rejected):

| Field | Type | Rule |
|---|---|---|
| `senior_citizen` | integer | 0 or 1 |
| `tenure_months` | integer | 0–72 |
| `monthly_charges` | number | 0–500 |
| `total_charges` | number | 0–50000 |
| `gender` | string | `female`, `male` |
| `partner` | string | `yes`, `no` |
| `contract` | string | `month-to-month`, `one-year`, `two-year` |
| `internet_service` | string | `dsl`, `fiber`, `none` |
| `payment_method` | string | `card`, `bank-transfer`, `electronic-check`, `mailed-check` |
| `paperless_billing` | string | `yes`, `no` |

Bounds are wider than or equal to what the model saw in training (synthetic data, see Project 01), so they guard against nonsense input and do not claim the model is accurate across the whole range.

Response (200):

```json
{
  "model_id": "churn-v1",
  "model_version": "1",
  "predictions": [{"churn_probability": 0.943, "churn": true}]
}
```

`predictions` has the same length and order as `instances`. `churn` is `churn_probability >= 0.5` (threshold from the manifest).

### GET /version

```json
{"app_version": "0.1.0", "model_id": "churn-v1", "model_version": "1", "source_revision": null}
```

`source_revision` comes from the optional `SOURCE_REVISION` environment variable (set at image build time) and is `null` otherwise.

## Error contract

Every non-2xx response from `/predict`, `/version`, unknown paths and unexpected exceptions uses this body. (`/health/*` use the status bodies above.)

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed.",
    "request_id": "3f6c2b8e-6a7d-4d0e-9b53-0c1b2f8a9d11",
    "details": [{"field": "instances.0.tenure_months", "issue": "Input should be less than or equal to 72"}]
  }
}
```

| HTTP | `code` | When |
|---|---|---|
| 404 | `not_found` | Unknown path |
| 405 | `not_found` | Known path, wrong method |
| 413 | `payload_too_large` | Body over 256 KiB, by `Content-Length` or by bytes actually received (chunked) |
| 422 | `validation_error` | Malformed JSON, missing or unknown field, wrong type, out-of-range value, bad category, empty or oversized batch. `details` lists each problem; the input value is never echoed. |
| 500 | `internal_error` | Any unhandled exception. Fixed message, no details; the cause is logged server-side with the request ID. |
| 503 | `model_not_ready` | `/predict` called while no verified model is loaded. Includes `Retry-After: 5`. |

## Startup and readiness semantics

1. The process starts and `/health/live` returns 200 immediately.
2. During startup the loader reads the manifest, checks the artifact exists, verifies its SHA-256, checks the runtime scikit-learn version matches the manifest, loads it once, and checks the manifest feature list matches the model's expected input columns. A smoke prediction on a fixed row must succeed.
3. Only then does `/health/ready` return 200 and `/predict` serve traffic.
4. If any step fails, the service **stays up but not ready**: the failure is logged (reason, no paths in responses), `/health/ready` and `/predict` return 503, and `/version` reports null model fields. An orchestrator should stop routing traffic based on readiness and restart or roll back based on its own policy.
5. There is no in-place reload. Changing the model means changing `MODEL_DIR` and restarting the process (see the runbook).

## Configuration (environment variables, validated at startup)

| Variable | Default | Meaning |
|---|---|---|
| `MODEL_DIR` | `models/churn-v1` | Directory holding `manifest.json` and the artifact |
| `MAX_BATCH_SIZE` | 100 | Upper bound for `instances`. Can lower the limit, never raise it above 100 (a larger batch gets 422). |
| `LOG_LEVEL` | `INFO` | Standard Python level names |
| `SOURCE_REVISION` | unset | Reported by `/version` |
| `PORT` | 8000 | Uvicorn listen port |
