# Decisions

1. **Artifact copied into this repo** (`models/churn-v1/`) with a `manifest.json` holding model id/version, library versions, feature schema, threshold and SHA-256. The repo stays independently runnable and the loader can verify existence, compatibility and schema agreement. It is a 6 KB synthetic-data model, so committing it is safe.
2. **joblib is pickle.** Loading executes code. The loader verifies the manifest SHA-256 before `joblib.load`, and the artifact directory is treated as trusted input only. Safer alternative: re-export with skops from Project 01. Deferred; listed as a known limitation.
3. **No MLflow client.** Optional in the spec and not justified for a local artifact.
4. **`prometheus-client` for metrics.** The spec requires operational visibility; labels are bounded (endpoint template, status class, outcome). Request IDs are never labels.
5. **Pins.** Python 3.12; scikit-learn 1.9.1 and joblib 1.6.0 match Project 01's lockfile, which wrote the artifact. Locust sits in a separate `load` group for load testing.
