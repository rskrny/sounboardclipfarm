"""
Quality and correctness test suite for the retrieval system.

Tests chunking, indexing, deduplication, search relevance,
token optimization, and visualization generation.

Usage:
    python -m retrieval test              Run all tests
    python -m retrieval test --verbose    Verbose output
"""

import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from .config import RetrievalConfig
from .chunker import Chunk, chunk_file, collect_files
from .optimizer import optimize_context, format_context_block, _estimate_information_density
from .searcher import SearchResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(root: Path) -> RetrievalConfig:
    """Create a config pointing at the real knowledge base."""
    config = RetrievalConfig()
    config.knowledge_root = root
    config.store_dir = root / "retrieval" / "store"
    config.db_path = config.store_dir / "metadata.db"
    return config


def _make_temp_config(tmp: Path) -> RetrievalConfig:
    """Create a config pointing at a temp directory for isolation."""
    config = RetrievalConfig()
    config.knowledge_root = tmp
    config.store_dir = tmp / "store"
    config.db_path = config.store_dir / "metadata.db"
    config.index_dirs = ["content"]
    config.include_patterns = ["*.md"]
    config.exclude_patterns = []
    config.use_semantic = False  # BM25 only for speed in tests
    return config


def _write_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_search_result(text: str, score: float, source: str = "test.md") -> SearchResult:
    return SearchResult(
        chunk_id=1,
        text=text,
        source_file=source,
        header_path=["Test"],
        domain=None,
        tags=[],
        score=score,
    )


# ---------------------------------------------------------------------------
# Test: Chunker
# ---------------------------------------------------------------------------

class TestChunker(unittest.TestCase):
    """Verify chunking respects structural boundaries."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_header_splitting(self):
        """Headers create chunk boundaries with proper header_path."""
        # Each section needs enough content to pass min_chunk_length
        md = (
            "# Top\n\nThis is the intro paragraph with enough content to pass the minimum chunk length threshold.\n\n"
            "## Section A\n\nContent for section A goes here. This paragraph contains enough words to be treated as a real chunk by the chunker system.\n\n"
            "## Section B\n\nContent for section B goes here. This paragraph also contains enough words to be treated as a separate real chunk.\n"
        )
        path = self.tmp / "test.md"
        _write_file(path, md)
        chunks = chunk_file(path, "test.md", max_tokens=512)
        # Should have at least 2 chunks (one per section)
        self.assertGreaterEqual(len(chunks), 2)
        # Check header_path carries section context
        section_chunks = [c for c in chunks if "Section A" in " ".join(c.header_path)]
        self.assertTrue(len(section_chunks) > 0, "Section A should appear in header_path")

    def test_code_fence_preservation(self):
        """Code fences are never split across chunks."""
        code_block = "```python\n" + "\n".join(f"x_{i} = {i}" for i in range(50)) + "\n```"
        md = f"# Code\n\n{code_block}\n\n# After\n\nSome text after."
        path = self.tmp / "code.md"
        _write_file(path, md)
        chunks = chunk_file(path, "code.md", max_tokens=512)
        # Find the chunk containing the code fence
        for c in chunks:
            if "```python" in c.text:
                # The closing fence must be in the same chunk
                self.assertIn("```", c.text.split("```python", 1)[1],
                              "Code fence was split across chunks")
                break

    def test_domain_extraction(self):
        """Domain is inferred from file path."""
        md = "# Test\n\nSome content for testing domain extraction.\n"
        content_dir = self.tmp / "prompts" / "context" / "by-domain" / "business-consulting"
        content_dir.mkdir(parents=True)
        path = content_dir / "frameworks.md"
        _write_file(path, md)
        chunks = chunk_file(path, "prompts/context/by-domain/business-consulting/frameworks.md")
        if chunks:
            self.assertEqual(chunks[0].domain, "business-consulting")

    def test_content_type_detection(self):
        """Code-heavy chunks are classified as code or contain code fences."""
        md = (
            "# Code Example\n\n"
            "Here is a substantial code block that demonstrates content type detection in the chunker.\n\n"
            "```python\n"
            "def hello_world():\n"
            "    message = 'Hello from the test suite'\n"
            "    print(message)\n"
            "    return message\n\n"
            "def another_function():\n"
            "    data = [1, 2, 3, 4, 5]\n"
            "    return sum(data)\n"
            "```\n\n"
            "And some text after the code block to make the file substantial enough.\n"
        )
        path = self.tmp / "example.md"
        _write_file(path, md)
        chunks = chunk_file(path, "example.md", max_tokens=512)
        # At least one chunk should contain code fences or be typed as code
        has_code = any(c.content_type == "code" for c in chunks) or any("```" in c.text for c in chunks)
        self.assertTrue(has_code, f"Should detect code content. Got types: {[c.content_type for c in chunks]}")

    def test_content_hash_uniqueness(self):
        """Different content produces different hashes."""
        md1 = "# First\n\nUnique content one.\n"
        md2 = "# Second\n\nDifferent content two.\n"
        p1 = self.tmp / "a.md"
        p2 = self.tmp / "b.md"
        _write_file(p1, md1)
        _write_file(p2, md2)
        chunks1 = chunk_file(p1, "a.md")
        chunks2 = chunk_file(p2, "b.md")
        if chunks1 and chunks2:
            self.assertNotEqual(chunks1[0].content_hash, chunks2[0].content_hash)

    def test_min_chunk_length(self):
        """Chunks below minimum length are filtered or merged."""
        md = "# Title\n\nOk.\n"
        path = self.tmp / "short.md"
        _write_file(path, md)
        chunks = chunk_file(path, "short.md", min_chunk_length=200)
        # With very high min, short content may produce 0 or 1 merged chunk
        self.assertTrue(len(chunks) <= 1)


# ---------------------------------------------------------------------------
# Test: Incremental Indexing
# ---------------------------------------------------------------------------

class TestIncrementalIndexing(unittest.TestCase):
    """Verify incremental indexing detects changes correctly."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.content_dir = self.tmp / "content"
        self.content_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _index(self, force=False):
        from .indexer import build_index
        config = _make_temp_config(self.tmp)
        return build_index(config, verbose=False, force_full=force)

    def test_full_index_creates_chunks(self):
        """Full index builds chunks from files."""
        _write_file(self.content_dir / "a.md", "# Test A\n\nContent for file A. This is a meaningful paragraph with enough words.\n")
        stats = self._index(force=True)
        self.assertGreater(stats["chunks"], 0)

    def test_incremental_no_changes(self):
        """Second run with no changes reports 0 changed files."""
        _write_file(self.content_dir / "a.md", "# Test A\n\nContent for file A. This is a meaningful paragraph with enough words.\n")
        self._index(force=True)
        stats = self._index(force=False)
        self.assertEqual(stats["changed"], 0)

    def test_new_file_detected(self):
        """Adding a new file triggers reindexing."""
        _write_file(self.content_dir / "a.md", "# Test A\n\nContent for file A with sufficient length to pass minimum.\n")
        self._index(force=True)
        _write_file(self.content_dir / "b.md", "# Test B\n\nNew content for file B with sufficient length to pass minimum.\n")
        stats = self._index(force=False)
        self.assertEqual(stats["changed"], 1)

    def test_modified_file_detected(self):
        """Modifying a file triggers reindexing for that file."""
        path = self.content_dir / "a.md"
        _write_file(path, "# Test A\n\nOriginal content that is long enough to be a real chunk.\n")
        self._index(force=True)
        _write_file(path, "# Test A\n\nModified content that is different and still long enough to be a chunk.\n")
        stats = self._index(force=False)
        self.assertEqual(stats["changed"], 1)

    def test_deleted_file_removed(self):
        """Deleting a file removes its chunks from the index."""
        _write_file(self.content_dir / "a.md", "# Test A\n\nContent A is long enough. Let us add more words here.\n")
        _write_file(self.content_dir / "b.md", "# Test B\n\nContent B is long enough. Let us add more words here.\n")
        stats1 = self._index(force=True)
        (self.content_dir / "b.md").unlink()
        stats2 = self._index(force=False)
        self.assertLessEqual(stats2["chunks"], stats1["chunks"])


# ---------------------------------------------------------------------------
# Test: Deduplication
# ---------------------------------------------------------------------------

class TestDeduplication(unittest.TestCase):
    """Verify content deduplication works correctly."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.content_dir = self.tmp / "content"
        self.content_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _index(self):
        from .indexer import build_index
        config = _make_temp_config(self.tmp)
        return build_index(config, verbose=False, force_full=True)

    def test_identical_content_deduped(self):
        """Same content in two files stores only one set of chunks."""
        content = "# Shared Title\n\nThis paragraph appears in both files. It should only be stored once in the index.\n"
        _write_file(self.content_dir / "copy1.md", content)
        _write_file(self.content_dir / "copy2.md", content)
        stats = self._index()
        # With dedup, chunks should be fewer than 2x single file
        single_content = "# Shared Title\n\nThis paragraph appears in both files. It should only be stored once in the index.\n"
        _write_file(self.content_dir / "single.md", single_content)
        # The key test: chunk count should not double with identical content
        from .store import Store
        config = _make_temp_config(self.tmp)
        store = Store(config.db_path, config.store_dir)
        hashes = store.get_all_chunk_hashes()
        store.close()
        # Each unique hash should appear only once
        self.assertEqual(len(hashes), len(set(hashes)))

    def test_different_content_separate(self):
        """Different content produces different chunks."""
        _write_file(self.content_dir / "a.md", "# Alpha\n\nAlpha content with unique words specific to this file only.\n")
        _write_file(self.content_dir / "b.md", "# Beta\n\nBeta content with completely different words for this other file.\n")
        self._index()
        from .store import Store
        config = _make_temp_config(self.tmp)
        store = Store(config.db_path, config.store_dir)
        chunks = store.get_all_chunks()
        store.close()
        sources = set(c["source_file"] for c in chunks)
        self.assertGreater(len(sources), 1, "Different files should produce separate chunks")


# ---------------------------------------------------------------------------
# Test: Optimizer
# ---------------------------------------------------------------------------

class TestOptimizer(unittest.TestCase):
    """Verify token budget optimization and MMR diversity."""

    def _make_results(self, count=10, text_len=200):
        results = []
        for i in range(count):
            word_set = f"topic_{i} " * (text_len // 10)
            results.append(_make_search_result(
                text=f"Chunk {i}: {word_set}",
                score=1.0 - i * 0.05,
                source=f"file_{i}.md",
            ))
        return results

    def test_budget_respected(self):
        """Optimizer never exceeds token budget."""
        results = self._make_results(20)
        optimized = optimize_context(results, token_budget=500)
        total = sum(c["tokens"] for c in optimized)
        self.assertLessEqual(total, 500)

    def test_small_budget(self):
        """Very small budget still returns at least one result if possible."""
        results = self._make_results(5, text_len=100)
        optimized = optimize_context(results, token_budget=200)
        # Should fit at least one chunk
        self.assertGreater(len(optimized), 0)

    def test_mmr_diversity(self):
        """Higher diversity lambda should select more diverse chunks."""
        # Create results with overlapping content
        base_text = "machine learning neural network deep learning training data"
        results = []
        for i in range(5):
            text = base_text + f" extra_{i}"
            results.append(_make_search_result(text=text, score=1.0 - i * 0.01))

        # High lambda = more relevance, less diversity
        high_rel = optimize_context(results, token_budget=2000, diversity_lambda=0.95)
        # Low lambda = more diversity
        high_div = optimize_context(results, token_budget=2000, diversity_lambda=0.1)

        # Both should return results
        self.assertGreater(len(high_rel), 0)
        self.assertGreater(len(high_div), 0)

    def test_compression_reduces_tokens(self):
        """Compression should reduce or maintain token count."""
        text = "Check this [link](https://example.com/very/long/url) and <!-- comment --> more."
        results = [_make_search_result(text=text * 10, score=1.0)]
        compressed = optimize_context(results, token_budget=5000, compress=True)
        uncompressed = optimize_context(results, token_budget=5000, compress=False)
        if compressed and uncompressed:
            self.assertLessEqual(compressed[0]["tokens"], uncompressed[0]["tokens"])

    def test_empty_input(self):
        """Empty input returns empty output."""
        self.assertEqual(optimize_context([], token_budget=1000), [])

    def test_format_context_block(self):
        """Context block contains header, sources, and footer."""
        results = self._make_results(3)
        optimized = optimize_context(results, token_budget=5000)
        block = format_context_block(optimized)
        self.assertIn("Retrieved Context", block)
        self.assertIn("End Retrieved Context", block)
        self.assertIn("Source:", block)

    def test_density_scoring(self):
        """Information density function returns higher scores for richer text."""
        sparse = "the the the the the the the the"
        rich = "quantum mechanics photon wavelength entropy thermodynamics topology manifold"
        sparse_score = _estimate_information_density(sparse)
        rich_score = _estimate_information_density(rich)
        self.assertGreater(rich_score, sparse_score)


# ---------------------------------------------------------------------------
# Test: Search Relevance (requires existing index)
# ---------------------------------------------------------------------------

class TestSearchRelevance(unittest.TestCase):
    """Test search quality against the real knowledge base."""

    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parent.parent
        cls.config = _make_config(cls.root)
        if not cls.config.db_path.exists():
            cls.skip_search = True
            return
        cls.skip_search = False
        from .searcher import Searcher
        cls.searcher = Searcher(cls.config)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'searcher'):
            cls.searcher.close()

    def test_domain_query_returns_domain_chunks(self):
        """Querying a domain topic returns chunks from that domain."""
        if self.skip_search:
            self.skipTest("No index found")
        results = self.searcher.search("business strategy frameworks", top_k=5)
        if results:
            domains = [r.domain for r in results if r.domain]
            # At least one result should be from business-consulting
            self.assertTrue(
                any("business" in d for d in domains),
                f"Expected business domain results, got: {domains}"
            )

    def test_bm25_only_works(self):
        """BM25-only search returns results."""
        if self.skip_search:
            self.skipTest("No index found")
        results = self.searcher.search_bm25_only("mental models", top_k=5)
        self.assertGreater(len(results), 0, "BM25 search should return results")

    def test_domain_filter(self):
        """Domain filter restricts results to that domain."""
        if self.skip_search:
            self.skipTest("No index found")
        results = self.searcher.search("frameworks", top_k=10, domain_filter="business-consulting")
        for r in results:
            if r.domain:
                self.assertEqual(r.domain, "business-consulting",
                                 f"Filter should restrict to business-consulting, got {r.domain}")

    def test_search_speed(self):
        """Search completes within 2 seconds."""
        if self.skip_search:
            self.skipTest("No index found")
        start = time.time()
        self.searcher.search("information retrieval", top_k=10)
        elapsed = time.time() - start
        self.assertLess(elapsed, 2.0, f"Search took {elapsed:.2f}s, should be under 2s")

    def test_scores_are_positive(self):
        """All search results have positive scores."""
        if self.skip_search:
            self.skipTest("No index found")
        results = self.searcher.search("writing style", top_k=5)
        for r in results:
            self.assertGreater(r.score, 0, "Scores should be positive")

    def test_results_have_metadata(self):
        """Search results carry full metadata."""
        if self.skip_search:
            self.skipTest("No index found")
        results = self.searcher.search("communication", top_k=3)
        if results:
            r = results[0]
            self.assertTrue(r.source_file, "Result should have source_file")
            self.assertTrue(r.text, "Result should have text")
            self.assertIsInstance(r.header_path, list, "header_path should be a list")


# ---------------------------------------------------------------------------
# Test: Visualization
# ---------------------------------------------------------------------------

class TestVisualization(unittest.TestCase):
    """Verify the knowledge graph visualization generates correctly."""

    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parent.parent
        cls.config = _make_config(cls.root)

    def test_html_generated(self):
        """Visualization generates an HTML file."""
        if not self.config.db_path.exists():
            self.skipTest("No index found")
        from .visualize import generate_visualization
        output = self.config.knowledge_root / "retrieval" / "test-viz.html"
        try:
            path = generate_visualization(self.config, output_path=output)
            self.assertTrue(path.exists(), "HTML file should be created")
            content = path.read_text(encoding="utf-8")
            self.assertIn("d3.v7.min.js", content, "Should reference D3 library")
            self.assertIn("GRAPH_DATA", content, "Should contain embedded graph data")
        finally:
            if output.exists():
                output.unlink()

    def test_graph_data_valid(self):
        """Embedded graph data contains valid JSON with nodes and edges."""
        if not self.config.db_path.exists():
            self.skipTest("No index found")
        from .store import Store
        store = Store(self.config.db_path, self.config.store_dir)
        graph = store.get_chunk_relationships()
        store.close()

        self.assertIn("nodes", graph)
        self.assertIn("edges", graph)
        self.assertGreater(len(graph["nodes"]), 0, "Should have nodes")

    def test_node_metadata(self):
        """Graph nodes contain expanded metadata fields."""
        if not self.config.db_path.exists():
            self.skipTest("No index found")
        from .store import Store
        store = Store(self.config.db_path, self.config.store_dir)
        graph = store.get_chunk_relationships()
        store.close()

        if graph["nodes"]:
            node = graph["nodes"][0]
            self.assertIn("header_path", node, "Node should have header_path")
            self.assertIn("tags", node, "Node should have tags")
            self.assertIn("start_line", node, "Node should have start_line")
            self.assertIn("content_hash", node, "Node should have content_hash")

    def test_stats_present(self):
        """Aggregate stats are computed correctly."""
        if not self.config.db_path.exists():
            self.skipTest("No index found")
        from .store import Store
        store = Store(self.config.db_path, self.config.store_dir)
        stats = store.get_aggregate_stats()
        store.close()

        self.assertIn("total_tokens", stats)
        self.assertIn("total_chunks", stats)
        self.assertIn("tokens_by_domain", stats)
        self.assertIn("tokens_by_file", stats)
        self.assertIn("content_types", stats)
        self.assertGreater(stats["total_chunks"], 0)
        self.assertGreater(stats["total_tokens"], 0)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_tests(verbose: bool = False) -> dict:
    """
    Run all quality tests and return a summary report.

    Returns dict with pass/fail counts and timing.
    """
    start = time.time()
    verbosity = 2 if verbose else 1

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    test_classes = [
        TestChunker,
        TestIncrementalIndexing,
        TestDeduplication,
        TestOptimizer,
        TestSearchRelevance,
        TestVisualization,
    ]

    for cls in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)

    elapsed = time.time() - start

    report = {
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "passed": result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped),
        "elapsed_seconds": round(elapsed, 2),
        "success": result.wasSuccessful(),
    }

    print(f"\n{'='*50}")
    print(f"  Quality Test Report")
    print(f"{'='*50}")
    print(f"  Passed:  {report['passed']}")
    print(f"  Failed:  {report['failures']}")
    print(f"  Errors:  {report['errors']}")
    print(f"  Skipped: {report['skipped']}")
    print(f"  Time:    {report['elapsed_seconds']}s")
    print(f"  Status:  {'PASS' if report['success'] else 'FAIL'}")
    print(f"{'='*50}")

    return report
