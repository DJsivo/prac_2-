import argparse
import asyncio
import statistics
import time

import httpx


async def _single_request(client: httpx.AsyncClient, url: str) -> float:
    started = time.perf_counter()
    response = await client.get(url)
    response.raise_for_status()
    return time.perf_counter() - started


async def run_load_test(base_url: str, path: str, requests: int, concurrency: int) -> None:
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    semaphore = asyncio.Semaphore(concurrency)
    latencies: list[float] = []

    async with httpx.AsyncClient(timeout=10.0) as client:
        async def worker() -> None:
            async with semaphore:
                latency = await _single_request(client, url)
                latencies.append(latency)

        started = time.perf_counter()
        await asyncio.gather(*[worker() for _ in range(requests)])
        total_time = time.perf_counter() - started

    print(f"URL: {url}")
    print(f"Requests: {requests}, concurrency: {concurrency}")
    print(f"Total time: {total_time:.3f}s")
    print(f"RPS: {requests / total_time:.2f}")
    print(f"Avg latency: {statistics.mean(latencies) * 1000:.2f} ms")
    if len(latencies) >= 20:
        p95 = statistics.quantiles(latencies, n=20)[18]
    else:
        p95 = max(latencies)
    print(f"P95 latency: {p95 * 1000:.2f} ms")
    print(f"Max latency: {max(latencies) * 1000:.2f} ms")


def main() -> None:
    parser = argparse.ArgumentParser(description="Simple async performance check for lab services.")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Gateway base URL")
    parser.add_argument("--path", default="/api/orders/orders", help="Path to test")
    parser.add_argument("--requests", type=int, default=100, help="Total request count")
    parser.add_argument("--concurrency", type=int, default=20, help="Parallel request count")
    args = parser.parse_args()

    if args.requests <= 0:
        raise ValueError("--requests must be > 0")
    if args.concurrency <= 0:
        raise ValueError("--concurrency must be > 0")

    asyncio.run(
        run_load_test(
            base_url=args.base_url,
            path=args.path,
            requests=args.requests,
            concurrency=args.concurrency,
        )
    )


if __name__ == "__main__":
    main()
