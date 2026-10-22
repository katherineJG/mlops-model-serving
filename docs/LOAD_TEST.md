# Load test

Measured on one machine, once, to see how the service behaves. This is **not** a capacity claim for any production environment.

## Workload

`loadtest/locustfile.py`, closed loop with no think time (each simulated user sends the next request as soon as the last returns):

- 90% `POST /predict` with 1 customer, 10% with a batch of 20.
- Customers generated from a fixed seed (42) within the documented field ranges.
- A response counts as a failure on any non-200 status or if the prediction count differs from the request.
- 10 s warm-up (discarded), then 45 s measured per level, stats reset after ramp-up.

## Environment

| | |
|---|---|
| CPU | AMD Ryzen 7 5800X (8 cores / 16 threads) |
| RAM | 31.9 GB host; Docker engine reports 16 CPUs, 15.6 GiB |
| OS / Docker | Windows 11 Home, Docker 29.8.2 (Linux engine) |
| Service | image `mlops-model-serving` built from this repo, `churn-v1` model, default settings (1 Uvicorn worker, no CPU limit, access log off) |
| Load generator | Locust 2.47.0, **single process, same machine** as the service |

## Results (single worker)

Raw CSVs are in `loadtest/results/`.

| Concurrent users | Requests | Failures | Throughput (req/s) | p50 (ms) | p95 (ms) | p99 (ms) | Container CPU |
|---|---|---|---|---|---|---|---|
| 4 | 8,156 | 0 | 184.7 | 21 | 26 | 29 | ~102% |
| 16 | 8,306 | 0 | 187.9 | 84 | 110 | 130 | ~102% |
| 64 | 8,344 | 0 | 188.6 | 340 | 400 | 420 | ~102% |

Latency percentiles are for all requests combined; single and 20-instance requests had essentially the same percentiles. Container memory stayed between 152 and 161 MiB.

## What this shows

- One worker saturates at roughly **185 requests/s**, about 5.3 ms of CPU per request. The container uses one full core at every level, so the worker is the limit.
- Past saturation, extra users only add queueing: latency grows linearly with concurrency (21 ms at 4 users, 340 ms at 64) while throughput stays flat.
- No errors at any level, including 64 users on one worker.
- A batch of 20 costs about the same wall time per request as a single customer in this run, so most per-request time is fixed overhead (DataFrame build and the sklearn pipeline call), not per-row work. This was not isolated with a dedicated experiment.

## Extra data point: 4 workers (not a clean measurement)

Same load with `--workers 4`, 16 users: 11,171 requests, 0 failures, **253 req/s**, p50 61 ms, p95 80 ms, p99 86 ms; container CPU ~154% and 524 MiB. Container CPU was well below 400%, which suggests the single-process Locust client became the limit, so treat 253 req/s as a lower bound on what 4 workers can do, not a measurement of it. Repeating it needs multiple Locust processes (`--processes`) or a separate machine.

## Limits of this test

- Load generator and service share one CPU complex and go through Docker Desktop networking.
- One run per level, no confidence intervals; differences of a few percent are noise.
- One payload mix. The model is small (logistic regression), so larger models would behave very differently.
- No soak test, no failure injection under load.

## Re-running

```bash
docker build -t mlops-model-serving:local .
docker run -d --name mss-load -p 127.0.0.1:8000:8000 mlops-model-serving:local
uv sync --group load
uv run python -m locust -f loadtest/locustfile.py --headless -u 16 -r 16 -t 45s \
  --reset-stats --host http://127.0.0.1:8000 --csv loadtest/results/users16
docker stats mss-load --no-stream        # run in a second terminal mid-test
docker rm -f mss-load
```

`python -m locust` is used instead of the `locust` executable because Application Control blocks the generated `.exe` launchers on the machine this was developed on.
