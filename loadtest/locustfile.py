"""Locust workload for the serving API (closed loop, no think time).

Mix: 90% single-customer /predict, 10% batch of 20. Customers are generated with a fixed seed,
so every run sends the same sequence of payload shapes. Run via docs/LOAD_TEST.md.
"""

import random

from locust import HttpUser, between, task

CONTRACTS = ["month-to-month", "one-year", "two-year"]
INTERNET = ["dsl", "fiber", "none"]
PAYMENT = ["card", "bank-transfer", "electronic-check", "mailed-check"]
YES_NO = ["yes", "no"]
BATCH_SIZE = 20

rng = random.Random(42)


def customer() -> dict[str, object]:
    tenure = rng.randint(0, 72)
    monthly = round(rng.uniform(15, 110), 2)
    return {
        "senior_citizen": rng.choice([0, 1]),
        "tenure_months": tenure,
        "monthly_charges": monthly,
        "total_charges": round(monthly * tenure, 2),
        "gender": rng.choice(["female", "male"]),
        "partner": rng.choice(YES_NO),
        "contract": rng.choice(CONTRACTS),
        "internet_service": rng.choice(INTERNET),
        "payment_method": rng.choice(PAYMENT),
        "paperless_billing": rng.choice(YES_NO),
    }


class ServingUser(HttpUser):
    wait_time = between(0, 0)

    def _predict(self, count: int, name: str) -> None:
        with self.client.post(
            "/predict",
            json={"instances": [customer() for _ in range(count)]},
            name=name,
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"status {response.status_code}")
            elif len(response.json()["predictions"]) != count:
                response.failure("prediction count mismatch")

    @task(9)
    def single(self) -> None:
        self._predict(1, "/predict (1 instance)")

    @task(1)
    def batch(self) -> None:
        self._predict(BATCH_SIZE, f"/predict ({BATCH_SIZE} instances)")
