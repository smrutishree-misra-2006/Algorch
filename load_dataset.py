"""
load_dataset.py — Download and index Wikipedia page titles into the Trie.

Wikipedia publishes a plain-text dump of all article titles (~6M lines).
We use this as a real-world dataset so benchmark numbers are meaningful.

Usage:
    python load_dataset.py                  # downloads + indexes everything
    python load_dataset.py --limit 100000   # only index first 100K titles

The script saves the processed titles to titles.txt so you don't have
to re-download on every run.
"""

import argparse
import gzip
import os
import time
import urllib.request
from typing import List, Tuple

DUMP_URL = "https://dumps.wikimedia.org/enwiki/latest/enwiki-latest-all-titles-in-ns0.gz"
LOCAL_GZ  = "enwiki_titles.gz"
LOCAL_TXT = "titles.txt"


def download_titles(limit: int = 0) -> List[str]:
    """
    Download Wikipedia title dump if not already cached locally.
    Returns a list of title strings (plain text, one per line).
    """
    if not os.path.exists(LOCAL_TXT):
        if not os.path.exists(LOCAL_GZ):
            print(f"Downloading Wikipedia title dump from:\n  {DUMP_URL}")
            print("(~250 MB compressed — this may take a few minutes)")
            urllib.request.urlretrieve(DUMP_URL, LOCAL_GZ,
                reporthook=lambda b, bs, ts: print(
                    f"  {min(b*bs, ts)/1e6:.1f} MB / {ts/1e6:.1f} MB", end="\r"))
            print()
        print("Decompressing...")
        with gzip.open(LOCAL_GZ, "rt", encoding="utf-8", errors="ignore") as f:
            lines = [l.strip().replace("_", " ") for l in f if l.strip()]
        with open(LOCAL_TXT, "w", encoding="utf-8") as out:
            out.write("\n".join(lines))
        print(f"Saved {len(lines):,} titles to {LOCAL_TXT}")
    else:
        with open(LOCAL_TXT, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        print(f"Loaded {len(lines):,} titles from cache ({LOCAL_TXT})")

    return lines[:limit] if limit else lines


def titles_to_freq_pairs(titles: List[str]) -> List[Tuple[str, int]]:
    """
    Assign a synthetic frequency to each title.
    In production you'd use real search-query logs; here we use title
    length as a rough proxy (shorter = more popular, like Wikipedia traffic).
    """
    return [(t, max(1, 100 - len(t))) for t in titles]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0,
                        help="Max titles to load (0 = all)")
    args = parser.parse_args()

    from trie import Trie
    titles = download_titles(limit=args.limit)
    pairs  = titles_to_freq_pairs(titles)

    print(f"\nIndexing {len(pairs):,} titles into Trie...")
    t0 = time.perf_counter()
    trie = Trie()
    trie.bulk_insert(pairs)
    elapsed = time.perf_counter() - t0

    print(f"Done. {trie.total_words:,} words indexed in {elapsed:.2f}s")
    print("\nSample queries:")
    for prefix in ["machine", "neural", "python", "deep learn", "india"]:
        results = trie.autocomplete(prefix, k=5)
        print(f"  '{prefix}' → {[w for w, _ in results]}")
