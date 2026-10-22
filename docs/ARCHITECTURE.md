# Architecture

```
Client
  -> FastAPI routing            (app/main.py)
  -> request-ID + logging middleware, exception mapping
  -> Pydantic validation        (app/schemas.py)
  -> inference service          (app/inference.py)
  -> loaded model               (app/model_loader.py reads models/churn-v1/)
  -> typed response
```

Cross-cutting: configuration (`app/config.py`), structured JSON logs (`app/logging_config.py`), Prometheus metrics, model metadata, health checks.

## Module responsibilities

| Module | Does | Does not |
|---|---|---|
| `config.py` | Reads and validates env vars at startup; fails fast on bad values | Touch the model |
| `model_loader.py` | Manifest parsing, SHA-256 and version checks, one-time load, smoke prediction; returns a `LoadedModel` or raises a typed error | Import FastAPI |
| `inference.py` | Turns validated `Customer` objects into a DataFrame in manifest column order, calls `predict_proba`, applies the threshold | Import FastAPI, read files |
| `schemas.py` | Request/response/error models | Contain logic |
| `main.py` | Lifespan (load model once), routes, middleware, exception handlers | Contain model logic |

The model loading and inference modules are built and tested without any HTTP.

## Model artifact

`models/<id>/manifest.json` plus `model.joblib`. The manifest records id, version, SHA-256, training library versions, feature schema and threshold. The loader trusts the manifest only after the checksum matches the artifact, and refuses to load otherwise.

## Concurrency and thread-safety assumptions

- The model is loaded once in the FastAPI lifespan and held as immutable app state. Nothing mutates it afterwards.
- `predict` is CPU-bound and synchronous. Route handlers are plain `def`, so FastAPI runs them in its threadpool and the event loop stays free for health checks.
- scikit-learn `Pipeline.predict_proba` on a fitted model does not mutate state, so concurrent calls from threads are safe for this pipeline (ColumnTransformer + LogisticRegression). This is an assumption about this model, not a general guarantee, and is covered by a concurrent-call test in the unit tests.
- Scale with multiple Uvicorn worker processes if needed; each loads its own copy. The container runs a single worker by default.

## Security and threat notes

- **Pickle risk:** `joblib.load` can execute code. Mitigation: checksum verification against a manifest that lives next to the artifact. This protects against corruption and accidental swaps, **not** against an attacker who can write both files. Treat `MODEL_DIR` as trusted, write-protected input. Safer format (skops) is a known follow-up.
- **No auth:** acceptable for a local/internal portfolio service; place behind an authenticating gateway for anything else. No admin or reload endpoints exist, by design.
- **Information disclosure:** a catch-all handler returns a fixed 500 body; validation errors never echo input values; logs omit request bodies.
- **Logging:** one JSON line per request with request ID, method, route template (not raw path), status, latency, model version, batch size. No payloads.
- **Metrics:** labels limited to route template, method, status class and outcome. Never request ID, user data or raw paths.
- **Resource limits:** 256 KiB body cap and 100-instance batch cap bound per-request work.

## Not in scope here

Drift monitoring, canary rollout, retraining, Kubernetes workflows (Projects 03–05).
