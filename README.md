# mlops-model-serving

HTTP inference API for a versioned churn model, built with FastAPI, Pydantic and Uvicorn. It shows what serving needs beyond calling `predict()`: explicit contracts, a verified model lifecycle, correct health semantics, safe errors, tests against the real HTTP service, and a non-root container.

The model comes from the *Reproducible ML Training Pipeline* project and is trained on **synthetic data**. It is a portfolio artifact, not for real customer decisions.

## Quick start (Docker)

```bash
docker build -t mlops-model-serving:local .
docker run -d --name mss -p 127.0.0.1:8000:8000 mlops-model-serving:local
curl -s localhost:8000/health/ready
```

Interactive API docs: <http://localhost:8000/docs>. Compose: `docker compose -f deployment/docker-compose.yml up --build`.

## Quick start (local, Python 3.12 and [uv](https://docs.astral.sh/uv/))

```bash
uv sync
uv run uvicorn app.main:app --port 8000
```

## Examples

```bash
curl -s -X POST localhost:8000/predict -H 'Content-Type: application/json' -d '{
  "instances": [{
    "senior_citizen": 0, "tenure_months": 3, "monthly_charges": 80.0, "total_charges": 240.0,
    "gender": "female", "partner": "no", "contract": "month-to-month",
    "internet_service": "fiber", "payment_method": "electronic-check", "paperless_billing": "yes"
  }]
}'
```

```json
{"model_id":"churn-v1","model_version":"1","predictions":[{"churn_probability":0.9430677139086144,"churn":true}]}
```

`GET /version`:

```json
{"app_version":"0.1.0","model_id":"churn-v1","model_version":"1","source_revision":null}
```

Invalid input (`tenure_months: 999`) returns 422 and never echoes the value:

```json
{"error":{"code":"validation_error","message":"Request validation failed.","request_id":"02df687a-9984-4772-aced-5278010d1bbd","details":[{"field":"instances.0.tenure_months","issue":"Input should be less than or equal to 72"}]}}
```

When the model could not be loaded, `/predict` returns 503 with `Retry-After: 5`:

```json
{"error":{"code":"model_not_ready","message":"Model is not ready.","request_id":"79aa53e2-6cc2-4c03-9edf-d330c904ed2b","details":[]}}
```

Full endpoint, field and error reference: [docs/API_CONTRACT.md](docs/API_CONTRACT.md).

## Configuration

Environment variables, validated at startup (bad values stop the process):

| Variable | Default | Meaning |
|---|---|---|
| `MODEL_DIR` | `models/churn-v1` | Directory with `manifest.json` and the model file |
| `MAX_BATCH_SIZE` | `100` | Max instances per request (can lower, not raise above 100) |
| `LOG_LEVEL` | `INFO` | Python logging level name |
| `SOURCE_REVISION` | unset | Reported by `/version` (set by `docker build --build-arg`) |
| `PORT` | `8000` | Port the app is configured for (the image's `CMD` listens on 8000) |

No credentials or cloud access are needed.

## Health semantics

- `GET /health/live`: process is up; never looks at the model.
- `GET /health/ready`: 200 only after the model passed verification (manifest, SHA-256, scikit-learn version, input schema, smoke prediction); otherwise 503.
- If verification fails the service stays up but not ready; `/predict` returns 503. Restart or roll back using your own policy.
- The model is loaded once at startup. There is no reload endpoint; a new model means a new image.

## Development

```bash
uv sync
uv run ruff check . && uv run ruff format --check . && uv run mypy app tests
uv run python -m pytest                      # unit, contract, ASGI and socket integration tests
MSS_IMAGE=mlops-model-serving:local uv run python -m pytest tests/integration/test_container.py
```

`make check`, `make docker-test` wrap the same commands (not run on the development machine, which has no `make`). `python -m pytest` is used because `pytest.exe` is blocked by Application Control there.

Load test: [docs/LOAD_TEST.md](docs/LOAD_TEST.md). Operations and rollback: [docs/RUNBOOK.md](docs/RUNBOOK.md). Design: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Why things are the way they are: [docs/DECISIONS.md](docs/DECISIONS.md). Criteria status with evidence: [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md).

## Troubleshooting

| Problem | What to check |
|---|---|
| `/health/ready` is 503 | `docker logs <container>` and look for `model load failed`; the `reason` field says why (for example `checksum_mismatch`) |
| Container exits immediately | Logs show which environment variable is invalid |
| 422 on `/predict` | `error.details[].field` names the offending field; allowed values are in the contract |
| `uv run pytest` fails to start on Windows | Use `uv run python -m pytest` (Application Control blocks the exe launcher) |
| Model fails with `version_mismatch` | The runtime scikit-learn differs from the version that wrote the model; use the locked environment |

## Security notes

No authentication (bind to loopback or an internal network). The model file is a pickle: a checksum protects against corruption, not against someone who can write the model and its manifest. See the runbook for details.

## Limitations

Synthetic-data model; single Uvicorn worker (about 185 req/s measured on one machine, see the load test for caveats); no TLS, auth, rate limiting or drift monitoring.
