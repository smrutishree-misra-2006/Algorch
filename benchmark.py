"""
benchmark.py — Measures autocomplete query latency at different dataset sizes.

Runs entirely in-process (no HTTP overhead), so this isolates pure
Trie algorithm performance — which is what you quote in the resume.

Usage:
    python benchmark.py                   # synthetic dataset
    python benchmark.py --titles titles.txt  # Wikipedia titles
"""

import argparse
import random
import statistics
import string
import time

from trie import Trie


def random_word(min_len=3, max_len=10):
    length = random.randint(min_len, max_len)
    return "".join(random.choices(string.ascii_lowercase, k=length))


def benchmark_at_size(n: int, titles=None, runs: int = 1000, k: int = 5):
    """Build a trie with n words, run `runs` prefix queries, report latencies."""
    trie = Trie()

    if titles:
        words = titles[:n]
        pairs = [(w, max(1, 100 - len(w))) for w in words]
    else:
        words = [random_word() for _ in range(n)]
        pairs = [(w, random.randint(1, 100)) for w in words]

    trie.bulk_insert(pairs)

    # Build prefixes from actual indexed words (guaranteed to have results)
    sample_words = random.sample(words, min(runs, len(words)))
    prefixes = [w[:random.randint(1, min(5, len(w)))] for w in sample_words]

    latencies = []
    for prefix in prefixes:
        t0 = time.perf_counter()
        trie.autocomplete(prefix, k=k)
        latencies.append((time.perf_counter() - t0) * 1000)

    latencies.sort()
    return {
        "n": n,
        "queries": len(latencies),
        "p50_ms": round(statistics.median(latencies), 4),
        "p95_ms": round(latencies[int(len(latencies) * 0.95) - 1], 4),
        "p99_ms": round(latencies[int(len(latencies) * 0.99) - 1], 4),
        "mean_ms": round(statistics.mean(latencies), 4),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--titles", type=str, default=None)
    parser.add_argument("--runs", type=int, default=1000,
                        help="Queries per dataset size")
    args = parser.parse_args()

    titles = None
    if args.titles:
        with open(args.titles, "r", encoding="utf-8") as f:
            titles = [l.strip() for l in f if l.strip()]
        print(f"Loaded {len(titles):,} titles from {args.titles}")

    sizes = [1_000, 10_000, 100_000, 500_000, 1_000_000]
    if titles:
        sizes = [s for s in sizes if s <= len(titles)]

    print(f"\n{'Dataset size':>14} | {'p50 (ms)':>10} | {'p95 (ms)':>10} | {'p99 (ms)':>10} | {'mean (ms)':>10}")
    print("-" * 65)
    for n in sizes:
        result = benchmark_at_size(n, titles=titles, runs=args.runs)
        print(f"{result['n']:>14,} | {result['p50_ms']:>10} | {result['p95_ms']:>10} | {result['p99_ms']:>10} | {result['mean_ms']:>10}")

    print("\nNote: these are in-process latencies (pure Trie algorithm,")
    print("no HTTP overhead). Add ~1-3ms for real network round-trip.")


if __name__ == "__main__":
    main()
