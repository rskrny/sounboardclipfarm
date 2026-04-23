"""
Command-line interface for the retrieval system.

Usage:
    python -m retrieval index                  Build/rebuild the search index
    python -m retrieval index --full           Force full rebuild (ignore cache)
    python -m retrieval search "query"         Search the knowledge base
    python -m retrieval search "query" -k 5 --domain business-consulting
    python -m retrieval search "query" --bm25-only   Skip semantic search
    python -m retrieval context "query"        Get optimized context block
    python -m retrieval viz                    Generate knowledge graph
    python -m retrieval viz --open             Generate and open in browser
    python -m retrieval stats                  Show index statistics
"""

import argparse
import sys
import os
from pathlib import Path

# Fix Windows console encoding for Unicode characters
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

from .config import RetrievalConfig


def cmd_index(args):
    """Build or rebuild the search index."""
    config = _load_config(args)
    force = getattr(args, "full", False)
    print(f"Indexing knowledge base at: {config.knowledge_root}")
    print(f"Directories: {config.index_dirs}")
    print(f"Mode: {'full rebuild' if force else 'incremental'}")
    print()

    from .indexer import build_index
    stats = build_index(config, verbose=True, force_full=force)
    return stats


def cmd_search(args):
    """Search the knowledge base."""
    config = _load_config(args)

    from .searcher import Searcher
    searcher = Searcher(config)

    if args.bm25_only:
        results = searcher.search_bm25_only(args.query, top_k=args.top_k)
    else:
        results = searcher.search(
            query=args.query,
            top_k=args.top_k,
            domain_filter=args.domain,
            file_filter=args.file,
        )

    if not results:
        print("No results found.")
        return

    print(f"\n{'='*70}")
    print(f"  Results for: \"{args.query}\"")
    print(f"  ({len(results)} results)")
    print(f"{'='*70}\n")

    for i, r in enumerate(results, 1):
        rank_info = []
        if r.bm25_rank is not None:
            rank_info.append(f"BM25:#{r.bm25_rank+1}")
        if r.semantic_rank is not None:
            rank_info.append(f"Semantic:#{r.semantic_rank+1}")

        print(f"  [{i}] {r.context_label}")
        print(f"      Score: {r.score:.4f}  |  {' | '.join(rank_info)}")
        if r.domain:
            print(f"      Domain: {r.domain}")
        if r.tags:
            print(f"      Tags: {', '.join(r.tags)}")
        # Show preview (first 200 chars)
        preview = r.text[:200].replace("\n", " ")
        if len(r.text) > 200:
            preview += "..."
        print(f"      {preview}")
        print()

    searcher.close()


def cmd_stats(args):
    """Show index statistics."""
    config = _load_config(args)

    from .searcher import Searcher
    searcher = Searcher(config)
    stats = searcher.get_stats()

    print(f"\nIndex Statistics")
    print(f"{'='*40}")
    print(f"  Total chunks: {stats['total_chunks']}")
    print(f"  BM25 loaded:  {stats['bm25_loaded']}")
    print(f"  Semantic:     {stats['semantic_loaded']}")
    print(f"  Last indexed: {stats['last_indexed']}")
    print(f"\n  Domains: {', '.join(stats['domains']) if stats['domains'] else 'none'}")
    print(f"\n  Files indexed:")
    for f in stats["files"]:
        print(f"    - {f}")

    searcher.close()


def cmd_context(args):
    """Get an optimized context block for a query."""
    config = _load_config(args)

    from .searcher import Searcher
    from .optimizer import optimize_context, format_context_block

    searcher = Searcher(config)
    results = searcher.search(query=args.query, top_k=20, domain_filter=args.domain)
    searcher.close()

    optimized = optimize_context(
        results,
        token_budget=args.budget,
        compress=True,
    )

    if not optimized:
        print("No relevant context found.")
        return

    block = format_context_block(optimized)
    print(block)
    print(f"\n--- {len(optimized)} chunks, ~{sum(c['tokens'] for c in optimized)} tokens ---")


def cmd_viz(args):
    """Generate knowledge graph visualization."""
    config = _load_config(args)

    from .visualize import generate_visualization
    path = generate_visualization(config, open_browser=args.open)
    print(f"Knowledge graph generated: {path}")
    if not args.open:
        print("Run with --open to view in browser")


def cmd_test(args):
    """Run quality tests."""
    from .test_quality import run_tests
    verbose = getattr(args, "verbose", False)
    report = run_tests(verbose=verbose)
    if not report["success"]:
        sys.exit(1)


def _load_config(args) -> RetrievalConfig:
    """Build config from CLI args."""
    root = Path(args.root).resolve()
    config_path = root / "retrieval" / "config.yaml"

    if config_path.exists():
        config = RetrievalConfig.from_yaml(config_path)
    else:
        config = RetrievalConfig()

    config.knowledge_root = root
    config.store_dir = root / "retrieval" / "store"
    config.db_path = config.store_dir / "metadata.db"
    return config


def main():
    parser = argparse.ArgumentParser(
        description="Context Engineering Retrieval System"
    )
    parser.add_argument(
        "--root", default=".",
        help="Path to the knowledge base root directory"
    )
    subparsers = parser.add_subparsers(dest="command")

    # index
    sub_index = subparsers.add_parser("index", help="Build/rebuild the search index")
    sub_index.add_argument("--full", action="store_true", help="Force full rebuild")

    # search
    sub_search = subparsers.add_parser("search", help="Search the knowledge base")
    sub_search.add_argument("query", help="Search query")
    sub_search.add_argument("-k", "--top-k", type=int, default=10)
    sub_search.add_argument("--domain", help="Filter by domain")
    sub_search.add_argument("--file", help="Filter by file path substring")
    sub_search.add_argument(
        "--bm25-only", action="store_true",
        help="Use BM25 only (no semantic search, no ML dependencies)"
    )

    # context
    sub_ctx = subparsers.add_parser("context", help="Get optimized context block")
    sub_ctx.add_argument("query", help="What context do you need?")
    sub_ctx.add_argument("--budget", type=int, default=4000, help="Token budget")
    sub_ctx.add_argument("--domain", help="Filter by domain")

    # viz
    sub_viz = subparsers.add_parser("viz", help="Generate knowledge graph visualization")
    sub_viz.add_argument("--open", action="store_true", help="Open in browser")

    # stats
    sub_stats = subparsers.add_parser("stats", help="Show index statistics")

    # test
    sub_test = subparsers.add_parser("test", help="Run quality tests")
    sub_test.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    commands = {
        "index": cmd_index,
        "search": cmd_search,
        "context": cmd_context,
        "viz": cmd_viz,
        "stats": cmd_stats,
        "test": cmd_test,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
