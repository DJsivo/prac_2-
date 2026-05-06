import argparse
import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import statistics
import sys
import time

import httpx
import matplotlib.pyplot as plt

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


@dataclass
class Sample:
    method: str
    run_no: int
    latency_ms: float
    order_id: int


def ensure_test_user(base_url: str, email: str, password: str, timeout: float) -> tuple[int, str]:
    register_payload = {"email": email, "password": password}
    login_payload = {"email": email, "password": password}

    with httpx.Client(timeout=timeout, trust_env=False) as client:
        # Wait for gateway/auth readiness (retries for fresh docker start).
        for _ in range(30):
            try:
                health = client.get(f"{base_url}/api/auth/health")
                if health.status_code == 200:
                    break
            except httpx.RequestError:
                pass
            time.sleep(1)

        response = None
        for _ in range(15):
            try:
                response = client.post(f"{base_url}/api/auth/register", json=register_payload)
                if response.status_code == 201:
                    token = response.json()["access_token"]
                    me = client.get(
                        f"{base_url}/api/auth/me",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    me.raise_for_status()
                    return int(me.json()["user_id"]), token
                if response.status_code < 500:
                    break
            except httpx.RequestError:
                pass
            time.sleep(1)

        if response is not None and response.status_code >= 500:
            raise RuntimeError(f"Auth register is unavailable: HTTP {response.status_code}")

        # Existing user flow: retry login because auth may still be warming up.
        login = None
        for _ in range(15):
            try:
                login = client.post(f"{base_url}/api/auth/login", json=login_payload)
                if login.status_code < 500:
                    break
            except httpx.RequestError:
                pass
            time.sleep(1)

        if login is None:
            raise RuntimeError("Auth service did not respond for login")
        login.raise_for_status()
        token = login.json()["access_token"]
        me = client.get(
            f"{base_url}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        me.raise_for_status()
        return int(me.json()["user_id"]), token


def run_one_method(
    base_url: str,
    method: str,
    user_id: int,
    access_token: str,
    runs: int,
    warmup: int,
    timeout: float,
) -> list[Sample]:
    samples: list[Sample] = []
    endpoint = f"{base_url}/api/orders/orders/{method}"
    headers = {"Authorization": f"Bearer {access_token}"}

    with httpx.Client(timeout=timeout, trust_env=False) as client:
        for idx in range(1, warmup + 1):
            payload = {
                "user_id": user_id,
                "total_amount": float(100 + idx),
                "notify_method": method,
            }
            _ = client.post(endpoint, json=payload, headers=headers)

        for run_no in range(1, runs + 1):
            payload = {
                "user_id": user_id,
                "total_amount": float(1000 + run_no),
                "notify_method": method,
            }
            started = time.perf_counter()
            response = client.post(endpoint, json=payload, headers=headers)
            elapsed_ms = (time.perf_counter() - started) * 1000
            response.raise_for_status()
            order_id = int(response.json()["id"])
            samples.append(Sample(method=method, run_no=run_no, latency_ms=elapsed_ms, order_id=order_id))

    return samples


def save_csv(samples: list[Sample], out_csv: Path) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["method", "run_no", "latency_ms", "order_id"])
        for sample in samples:
            writer.writerow([sample.method, sample.run_no, f"{sample.latency_ms:.4f}", sample.order_id])


def save_summary(samples: list[Sample], out_summary: Path, runs: int, warmup: int, base_url: str) -> None:
    out_summary.parent.mkdir(parents=True, exist_ok=True)
    methods = sorted({s.method for s in samples})
    lines: list[str] = []
    lines.append("Full-chain transport benchmark (gateway -> orders -> auth + notification + tracking + DB)")
    lines.append(f"base_url: {base_url}")
    lines.append(f"runs_per_method: {runs}")
    lines.append(f"warmup_per_method: {warmup}")
    lines.append("")
    lines.append("| Method | Mean (ms) | Variance (ms^2) | Min (ms) | Max (ms) |")
    lines.append("|---|---:|---:|---:|---:|")

    stats: list[tuple[str, float, float]] = []
    for method in methods:
        values = [s.latency_ms for s in samples if s.method == method]
        mean_ms = statistics.mean(values)
        variance_ms2 = statistics.pvariance(values)
        min_ms = min(values)
        max_ms = max(values)
        stats.append((method, mean_ms, variance_ms2))
        lines.append(f"| {method} | {mean_ms:.2f} | {variance_ms2:.2f} | {min_ms:.2f} | {max_ms:.2f} |")

    best = min(stats, key=lambda item: item[1])
    lines.append("")
    lines.append(f"Fastest by mean latency: {best[0]} ({best[1]:.2f} ms)")

    out_summary.write_text("\n".join(lines), encoding="utf-8")


def save_plot(samples: list[Sample], out_png: Path) -> None:
    out_png.parent.mkdir(parents=True, exist_ok=True)
    methods = sorted({s.method for s in samples})
    plt.figure(figsize=(10, 5))
    for method in methods:
        method_samples = sorted((s for s in samples if s.method == method), key=lambda s: s.run_no)
        x = [s.run_no for s in method_samples]
        y = [s.latency_ms for s in method_samples]
        plt.plot(x, y, label=method)

    plt.title("Latency by call number (full chain)")
    plt.xlabel("Call number")
    plt.ylabel("Latency, ms")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_png, dpi=140)
    plt.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark full chain request for http/msgpack/grpc and save csv/summary/plot."
    )
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--runs", type=int, default=100)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--email", default="demo_show@example.com")
    parser.add_argument("--password", default="strongpass123")
    parser.add_argument("--out-dir", default="reports/performance_fullchain")
    args = parser.parse_args()

    if args.runs < 100:
        raise ValueError("--runs must be >= 100 to satisfy lab requirement")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out_dir)
    out_csv = out_dir / f"full_chain_samples_{ts}.csv"
    out_summary = out_dir / f"full_chain_summary_{ts}.txt"
    out_png = out_dir / f"full_chain_plot_{ts}.png"

    user_id, access_token = ensure_test_user(args.base_url, args.email, args.password, args.timeout)
    all_samples: list[Sample] = []
    for method in ["http", "msgpack", "grpc"]:
        all_samples.extend(
            run_one_method(
                base_url=args.base_url,
                method=method,
                user_id=user_id,
                access_token=access_token,
                runs=args.runs,
                warmup=args.warmup,
                timeout=args.timeout,
            )
        )

    save_csv(all_samples, out_csv)
    save_summary(all_samples, out_summary, args.runs, args.warmup, args.base_url)
    save_plot(all_samples, out_png)

    print(f"Saved samples: {out_csv}")
    print(f"Saved summary: {out_summary}")
    print(f"Saved plot: {out_png}")


if __name__ == "__main__":
    main()
