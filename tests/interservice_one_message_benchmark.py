import argparse
import json
import statistics
import time
from dataclasses import dataclass

import grpc
import httpx
import msgpack


@dataclass
class BenchResult:
    method: str
    samples_ms: list[float]

    @property
    def min_ms(self) -> float:
        return min(self.samples_ms)

    @property
    def max_ms(self) -> float:
        return max(self.samples_ms)

    @property
    def avg_ms(self) -> float:
        return statistics.mean(self.samples_ms)

    @property
    def p95_ms(self) -> float:
        if len(self.samples_ms) >= 20:
            return statistics.quantiles(self.samples_ms, n=20)[18]
        return max(self.samples_ms)


def send_one(
    client: httpx.Client,
    base_url: str,
    grpc_rpc,
    method: str,
    user_id: int,
    message_seq: int,
) -> float:
    payload: dict = {
        "user_id": user_id,
        "order_id": None,
        "message": f"bench message #{message_seq}",
    }

    if method == "grpc":
        started = time.perf_counter()
        grpc_rpc(payload, timeout=5.0)
        return (time.perf_counter() - started) * 1000

    url = f"{base_url.rstrip('/')}/internal/order-created/{method}"
    started = time.perf_counter()
    if method == "msgpack":
        response = client.post(
            url,
            content=msgpack.packb(payload, use_bin_type=True),
            headers={"content-type": "application/msgpack"},
        )
    else:
        response = client.post(url, json=payload)

    elapsed_ms = (time.perf_counter() - started) * 1000
    response.raise_for_status()
    return elapsed_ms


def run_benchmark(
    base_url: str,
    grpc_url: str,
    runs: int,
    warmup: int,
    user_id: int,
    timeout: float,
) -> list[BenchResult]:
    methods = ["http", "msgpack", "grpc"]
    results: list[BenchResult] = []

    with httpx.Client(timeout=timeout) as client:
        with grpc.insecure_channel(grpc_url) as grpc_channel:
            grpc_rpc = grpc_channel.unary_unary(
                "/notification.NotificationService/CreateOrderNotification",
                request_serializer=lambda data: json.dumps(data).encode("utf-8"),
                response_deserializer=lambda raw: json.loads(raw.decode("utf-8")),
            )

            message_seq = 1
            for method in methods:
                for _ in range(warmup):
                    _ = send_one(client, base_url, grpc_rpc, method, user_id, message_seq)
                    message_seq += 1

                samples: list[float] = []
                for _ in range(runs):
                    samples.append(send_one(client, base_url, grpc_rpc, method, user_id, message_seq))
                    message_seq += 1

                results.append(BenchResult(method=method, samples_ms=samples))

    return results


def print_results(results: list[BenchResult], runs: int, base_url: str) -> None:
    print("Inter-service benchmark: one message send latency")
    print(f"Target service URL: {base_url}")
    print(f"Measured requests per method: {runs}")
    print()
    print("| Method | Min (ms) | Avg (ms) | P95 (ms) | Max (ms) |")
    print("|---|---:|---:|---:|---:|")
    for item in results:
        print(
            f"| {item.method} | {item.min_ms:.2f} | {item.avg_ms:.2f} | {item.p95_ms:.2f} | {item.max_ms:.2f} |"
        )

    fastest = min(results, key=lambda item: item.avg_ms)
    print()
    print(f"Fastest by average latency: {fastest.method} ({fastest.avg_ms:.2f} ms)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure one-message latency between services for http/msgpack/grpc endpoints."
    )
    parser.add_argument(
        "--base-url",
        default="http://notification:8004",
        help="Receiver service URL (default is container-to-container notification service)",
    )
    parser.add_argument(
        "--grpc-url",
        default="notification:50051",
        help="Receiver gRPC URL (host:port)",
    )
    parser.add_argument("--runs", type=int, default=30, help="Measured requests per method")
    parser.add_argument("--warmup", type=int, default=5, help="Warmup requests per method")
    parser.add_argument("--user-id", type=int, default=1, help="User ID for payload")
    parser.add_argument("--timeout", type=float, default=5.0, help="Request timeout in seconds")
    args = parser.parse_args()

    if args.runs <= 0:
        raise ValueError("--runs must be > 0")
    if args.warmup < 0:
        raise ValueError("--warmup must be >= 0")

    results = run_benchmark(
        base_url=args.base_url,
        grpc_url=args.grpc_url,
        runs=args.runs,
        warmup=args.warmup,
        user_id=args.user_id,
        timeout=args.timeout,
    )
    print_results(results, runs=args.runs, base_url=args.base_url)


if __name__ == "__main__":
    main()
