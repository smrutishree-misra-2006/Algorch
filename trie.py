"""
trie.py — Trie data structure with frequency-ranked prefix search.

Core operations (all O(L) where L = length of the query string):
  insert(word, frequency)  — add a word with a search frequency count
  search(word)             — exact match check
  autocomplete(prefix, k)  — top-k completions ranked by frequency

Design decisions worth explaining in interviews:
  - Each TrieNode stores a dict of children (vs a fixed 26-char array)
    so the trie works for any unicode characters, not just a-z.
  - Frequency is stored at the terminal node; autocomplete uses a
    max-heap to avoid sorting all completions (keeps it O(M log k)
    where M = number of nodes under the prefix).
  - Thread-safety: a single RWLock pattern would be ideal; here we use
    a threading.Lock for simplicity — same reasoning as MiniKV shard locks.
"""

import heapq
import threading
from typing import List, Optional, Tuple


class TrieNode:
    __slots__ = ("children", "frequency", "is_terminal")

    def __init__(self):
        self.children: dict[str, "TrieNode"] = {}
        self.frequency: int = 0       # 0 means not a complete word here
        self.is_terminal: bool = False


class Trie:
    def __init__(self):
        self.root = TrieNode()
        self._lock = threading.Lock()
        self._total_words = 0

    # ---------- insert ----------

    def insert(self, word: str, frequency: int = 1) -> None:
        """Insert word with a given frequency (higher = ranked first)."""
        word = word.lower().strip()
        if not word:
            return
        with self._lock:
            node = self.root
            for ch in word:
                if ch not in node.children:
                    node.children[ch] = TrieNode()
                node = node.children[ch]
            if not node.is_terminal:
                self._total_words += 1
            node.is_terminal = True
            node.frequency = max(node.frequency, frequency)  # keep highest seen

    def bulk_insert(self, words_with_freq: List[Tuple[str, int]]) -> None:
        """
        Faster bulk insert: acquires the lock once for the whole batch.
        Use this when loading a large dataset (e.g. Wikipedia titles).
        """
        with self._lock:
            for word, freq in words_with_freq:
                word = word.lower().strip()
                if not word:
                    continue
                node = self.root
                for ch in word:
                    if ch not in node.children:
                        node.children[ch] = TrieNode()
                    node = node.children[ch]
                if not node.is_terminal:
                    self._total_words += 1
                node.is_terminal = True
                node.frequency = max(node.frequency, freq)

    # ---------- search ----------

    def search(self, word: str) -> bool:
        """Exact match — O(L)."""
        node = self._node_for_prefix(word.lower().strip())
        return node is not None and node.is_terminal

    def starts_with(self, prefix: str) -> bool:
        """Returns True if any word in the trie starts with prefix — O(L)."""
        return self._node_for_prefix(prefix.lower().strip()) is not None

    # ---------- autocomplete ----------

    def autocomplete(self, prefix: str, k: int = 5) -> List[Tuple[str, int]]:
        """
        Return up to k completions for prefix, ranked by frequency descending.

        Returns list of (word, frequency) tuples.

        Complexity: O(L + M log k) where L = len(prefix),
                    M = number of trie nodes under the prefix node.
        """
        prefix = prefix.lower().strip()
        with self._lock:
            node = self._node_for_prefix_locked(prefix)
            if node is None:
                return []
            # Walk the subtree under `node`, collecting all terminal nodes.
            # Use a min-heap of size k to track top-k by frequency.
            heap: List[Tuple[int, str]] = []  # (frequency, word)
            self._dfs(node, prefix, heap, k)
        # heap is a min-heap of (freq, word); return sorted descending
        return [(word, freq) for freq, word in sorted(heap, reverse=True)]

    def _dfs(self, node: TrieNode, current: str,
             heap: list, k: int) -> None:
        """DFS from node; maintain a max-k min-heap by frequency."""
        if node.is_terminal:
            if len(heap) < k:
                heapq.heappush(heap, (node.frequency, current))
            elif node.frequency > heap[0][0]:
                heapq.heapreplace(heap, (node.frequency, current))
        for ch, child in node.children.items():
            self._dfs(child, current + ch, heap, k)

    # ---------- helpers ----------

    def _node_for_prefix(self, prefix: str) -> Optional[TrieNode]:
        with self._lock:
            return self._node_for_prefix_locked(prefix)

    def _node_for_prefix_locked(self, prefix: str) -> Optional[TrieNode]:
        """Caller must hold self._lock."""
        node = self.root
        for ch in prefix:
            if ch not in node.children:
                return None
            node = node.children[ch]
        return node

    # ---------- stats ----------

    @property
    def total_words(self) -> int:
        with self._lock:
            return self._total_words


if __name__ == "__main__":
    t = Trie()
    words = [
        ("apple", 100), ("application", 80), ("app", 60),
        ("appetizer", 30), ("apply", 50), ("apt", 20),
        ("google", 200), ("golang", 90), ("gorilla", 40),
        ("python", 150), ("pytorch", 110), ("pypi", 60),
    ]
    t.bulk_insert(words)

    print("=== Autocomplete demo ===")
    for prefix in ["app", "go", "py", "xyz"]:
        results = t.autocomplete(prefix, k=3)
        print(f"  '{prefix}' → {results}")

    print(f"\nTotal words indexed: {t.total_words}")
    print(f"'apple' exact match: {t.search('apple')}")
    print(f"'appl'  exact match: {t.search('appl')}")
    print(f"'appl'  starts_with: {t.starts_with('appl')}")
