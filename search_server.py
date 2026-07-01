"""
search_server.py — HTTP server exposing the Trie as an autocomplete API.

Endpoints:
  GET /suggest?q=<prefix>&k=<int>   → top-k suggestions
  GET /search?q=<word>              → exact match check
  POST /index  body: {"word": "...", "frequency": N}  → add a word live
  GET /stats                        → total words indexed, uptime

Run:
    # Quick demo (builds a small in-memory dataset):
    python search_server.py --demo

    # Full Wikipedia dataset (run load_dataset.py first):
    python search_server.py --titles titles.txt --port 8000
"""

import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from trie import Trie

trie: Trie = None
start_time: float = None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # suppress per-request noise; remove for debugging

    def _send_json(self, status: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        if parsed.path == "/suggest":
            prefix = qs.get("q", [""])[0].strip()
            k = int(qs.get("k", [5])[0])
            if not prefix:
                self._send_json(400, {"error": "q param required"})
                return
            t0 = time.perf_counter()
            results = trie.autocomplete(prefix, k=k)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            self._send_json(200, {
                "prefix": prefix,
                "suggestions": [{"word": w, "frequency": f} for w, f in results],
                "count": len(results),
                "latency_ms": round(elapsed_ms, 3)
            })

        elif parsed.path == "/search":
            word = qs.get("q", [""])[0].strip()
            if not word:
                self._send_json(400, {"error": "q param required"})
                return
            found = trie.search(word)
            self._send_json(200, {"word": word, "found": found})

        elif parsed.path == "/stats":
            self._send_json(200, {
                "total_words": trie.total_words,
                "uptime_seconds": round(time.time() - start_time, 1)
            })

        else:
            self._send_json(404, {"error": "unknown route"})

    def do_POST(self):
        if urlparse(self.path).path == "/index":
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                self._send_json(400, {"error": "invalid json"})
                return
            word = data.get("word", "").strip()
            freq = int(data.get("frequency", 1))
            if not word:
                self._send_json(400, {"error": "word required"})
                return
            trie.insert(word, frequency=freq)
            self._send_json(200, {"ok": True, "word": word, "frequency": freq})
        else:
            self._send_json(404, {"error": "unknown route"})


def load_from_file(path: str):
    print(f"Loading titles from {path}...")
    t0 = time.perf_counter()
    pairs = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            word = line.strip()
            if word:
                pairs.append((word, max(1, 100 - len(word))))
    trie.bulk_insert(pairs)
    print(f"Indexed {trie.total_words:,} words in {time.perf_counter()-t0:.2f}s")


def load_demo():
    demo_words = [
        ("machine learning", 95), ("machine learning engineer", 70),
        ("machine translation", 60), ("machines", 40),
        ("neural network", 90), ("neural machine translation", 65),
        ("natural language processing", 85), ("natural language", 75),
        ("python programming", 88), ("python tutorial", 72),
        ("pytorch", 80), ("pypi packages", 50),
        ("deep learning", 92), ("deep neural network", 78),
        ("google search", 99), ("google maps", 88), ("google cloud", 82),
        ("gradient descent", 70), ("graph neural network", 60),
        ("india", 95), ("indian cricket", 80), ("indian economy", 75),
        ("image recognition", 68), ("image segmentation", 55),
    ]
    trie.bulk_insert(demo_words)
    print(f"Demo mode: indexed {trie.total_words} words")


def main():
    global trie, start_time
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--titles", type=str, default=None,
                        help="Path to titles.txt from load_dataset.py")
    parser.add_argument("--demo", action="store_true",
                        help="Use a small built-in demo dataset")
    args = parser.parse_args()

    trie = Trie()
    start_time = time.time()

    if args.demo:
        load_demo()
    elif args.titles:
        load_from_file(args.titles)
    else:
        print("No dataset specified. Use --demo for quick start or "
              "--titles titles.txt for Wikipedia data.")
        print("Starting with empty trie (use POST /index to add words).")

    server = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    print(f"SearchTrie server on :{args.port}  ({trie.total_words:,} words indexed)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
