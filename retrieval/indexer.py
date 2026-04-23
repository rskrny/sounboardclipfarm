"""
Index builder with incremental indexing and deduplication.

Tracks file hashes so only changed files get re-indexed.
Deduplicates chunks by content hash to prevent redundancy.
"""

import re
import time
import hashlib
import logging
from pathlib import Path

from .config import RetrievalConfig
from .chunker import Chunk, chunk_file, collect_files
from .store import Store

logger = logging.getLogger("retrieval.indexer")


def _tokenize_for_bm25(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer for BM25."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    tokens = text.split()
    return [t for t in tokens if len(t) > 1]


def _file_hash(path: Path) -> str:
    """Compute SHA-256 hash of file contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            h.update(block)
    return h.hexdigest()[:32]


def build_index(
    config: RetrievalConfig,
    verbose: bool = True,
    force_full: bool = False,
) -> dict:
    """
    Build or incrementally update the search index.

    If force_full=False (default), only re-indexes files whose
    content hash has changed since the last build. This makes
    re-indexing fast even with thousands of files.

    Deduplication: chunks with identical content hashes are
    stored only once.
    """
    start = time.time()
    store = Store(config.db_path, config.store_dir)

    # 1. Collect files
    files = collect_files(
        config.knowledge_root,
        config.index_dirs,
        config.include_patterns,
        config.exclude_patterns,
    )
    if verbose:
        print(f"Found {len(files)} files to index")

    # 2. Check which files changed (incremental mode)
    changed_files = files
    unchanged_count = 0

    if not force_full:
        stored_hashes = store.get_file_hashes()
        changed_files = []
        current_hashes = {}

        for f in files:
            rel_path = str(f.relative_to(config.knowledge_root)).replace("\\", "/")
            fhash = _file_hash(f)
            current_hashes[rel_path] = fhash

            if stored_hashes.get(rel_path) != fhash:
                changed_files.append(f)
            else:
                unchanged_count += 1

        # Detect deleted files
        current_paths = set(current_hashes.keys())
        stored_paths = set(stored_hashes.keys())
        deleted_paths = stored_paths - current_paths

        if deleted_paths:
            if verbose:
                print(f"Removing {len(deleted_paths)} deleted files from index")
            for dp in deleted_paths:
                store.delete_chunks_by_file(dp)

        if verbose and unchanged_count > 0:
            print(f"Skipping {unchanged_count} unchanged files")

    if not changed_files and not force_full:
        if verbose:
            print("No changes detected. Index is up to date.")
        elapsed = time.time() - start
        chunk_count = store.chunk_count()
        store.close()
        return {
            "files": len(files),
            "chunks": chunk_count,
            "changed": 0,
            "bm25": True,
            "semantic": config.use_semantic,
            "elapsed_seconds": round(elapsed, 2),
        }

    # 3. Chunk changed files
    if force_full:
        store.clear_chunks()

    new_chunks: list[Chunk] = []
    seen_hashes: set[str] = set()

    # Load existing hashes for dedup
    if not force_full:
        seen_hashes = store.get_all_chunk_hashes()

    for f in changed_files:
        rel_path = str(f.relative_to(config.knowledge_root)).replace("\\", "/")

        if not force_full:
            store.delete_chunks_by_file(rel_path)

        try:
            chunks = chunk_file(
                file_path=f,
                source_file=rel_path,
                max_tokens=config.chunk_max_tokens,
                overlap_tokens=config.chunk_overlap_tokens,
                min_chunk_length=config.min_chunk_length,
                split_on_headers=config.split_on_headers,
            )
        except Exception as e:
            logger.warning(f"Failed to chunk {rel_path}: {e}")
            if verbose:
                print(f"  WARNING: Failed to chunk {rel_path}: {e}")
            continue

        # Dedup by content hash
        for chunk in chunks:
            if chunk.content_hash not in seen_hashes:
                new_chunks.append(chunk)
                seen_hashes.add(chunk.content_hash)

        # Update file hash
        fhash = _file_hash(f)
        store.set_file_hash(rel_path, fhash)

    if verbose:
        deduped = sum(1 for f in changed_files for _ in [1]) - len(new_chunks)
        print(f"Created {len(new_chunks)} chunks from {len(changed_files)} changed files")

    # 4. Insert new chunks
    store.insert_chunks(new_chunks)

    # 5. Rebuild BM25 index (always full rebuild -- BM25 is fast)
    if verbose:
        print("Building BM25 index...")

    all_chunks = store.get_all_chunks()
    corpus = [_tokenize_for_bm25(c["text"]) for c in all_chunks]

    from rank_bm25 import BM25Okapi
    bm25 = BM25Okapi(corpus, k1=config.bm25_k1, b=config.bm25_b)
    store.save_bm25(bm25)

    # 6. Rebuild vector index
    if config.use_semantic:
        if verbose:
            print(f"Building semantic index with {config.embedding_model}...")
        try:
            from sentence_transformers import SentenceTransformer
            import numpy as np

            model = SentenceTransformer(config.embedding_model)
            texts = [c["text"] for c in all_chunks]

            embeddings = model.encode(
                texts,
                show_progress_bar=verbose,
                batch_size=64,
                normalize_embeddings=True,
            )
            store.save_embeddings(embeddings)
            if verbose:
                print(f"Saved {len(embeddings)} embeddings ({config.embedding_dim}d)")
        except ImportError:
            if verbose:
                print(
                    "sentence-transformers not installed. "
                    "Running in BM25-only mode. "
                    "Install with: pip install sentence-transformers"
                )
            config.use_semantic = False

    # 7. Save metadata
    store.set_meta("last_indexed", str(time.time()))
    store.set_meta("file_count", str(len(files)))
    store.set_meta("chunk_count", str(len(all_chunks)))
    store.set_meta("semantic_enabled", str(config.use_semantic))
    store.set_meta("embedding_model", config.embedding_model)

    elapsed = time.time() - start
    stats = {
        "files": len(files),
        "chunks": len(all_chunks),
        "changed": len(changed_files),
        "new_chunks": len(new_chunks),
        "bm25": True,
        "semantic": config.use_semantic,
        "elapsed_seconds": round(elapsed, 2),
    }

    if verbose:
        print(f"\nIndex built in {stats['elapsed_seconds']}s")
        print(f"  Total files:    {stats['files']}")
        print(f"  Changed files:  {stats['changed']}")
        print(f"  Total chunks:   {stats['chunks']}")
        print(f"  New chunks:     {stats['new_chunks']}")
        print(f"  BM25:           {stats['bm25']}")
        print(f"  Semantic:       {stats['semantic']}")

    store.close()
    return stats
