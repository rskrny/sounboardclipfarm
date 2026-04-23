"""
Persistence layer with WAL mode, file tracking, and deduplication.

SQLite for metadata. File-based storage for BM25 and embeddings.
WAL mode for safe concurrent reads during MCP server operation.
"""

import json
import sqlite3
import pickle
from pathlib import Path
from typing import Optional
from functools import lru_cache

from .chunker import Chunk


class Store:
    """SQLite-backed storage with concurrency safety."""

    def __init__(self, db_path: Path, store_dir: Path):
        self.db_path = Path(db_path)
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(
            str(self.db_path),
            timeout=30,  # wait up to 30s for locks
        )
        self.conn.row_factory = sqlite3.Row
        # WAL mode: allows concurrent reads during writes
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=30000")
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                source_file TEXT NOT NULL,
                header_path TEXT,
                chunk_index INTEGER,
                start_line INTEGER,
                end_line INTEGER,
                content_type TEXT DEFAULT 'prose',
                domain TEXT,
                tags TEXT,
                token_estimate INTEGER,
                content_hash TEXT
            );

            CREATE TABLE IF NOT EXISTS file_hashes (
                file_path TEXT PRIMARY KEY,
                hash TEXT NOT NULL,
                last_indexed REAL
            );

            CREATE TABLE IF NOT EXISTS index_meta (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source_file);
            CREATE INDEX IF NOT EXISTS idx_chunks_domain ON chunks(domain);
            CREATE INDEX IF NOT EXISTS idx_chunks_hash ON chunks(content_hash);
            CREATE INDEX IF NOT EXISTS idx_chunks_type ON chunks(content_type);
        """)
        self.conn.commit()

    # --- Chunk operations ---

    def clear_chunks(self):
        self.conn.execute("DELETE FROM chunks")
        self.conn.execute("DELETE FROM file_hashes")
        self.conn.commit()

    def insert_chunks(self, chunks: list[Chunk]):
        rows = []
        for c in chunks:
            rows.append((
                c.text,
                c.source_file,
                json.dumps(c.header_path),
                c.chunk_index,
                c.start_line,
                c.end_line,
                c.content_type,
                c.domain,
                json.dumps(c.tags),
                len(c.text) // 4,
                c.content_hash,
            ))
        self.conn.executemany(
            """INSERT INTO chunks
               (text, source_file, header_path, chunk_index, start_line,
                end_line, content_type, domain, tags, token_estimate, content_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        self.conn.commit()

    def delete_chunks_by_file(self, file_path: str):
        self.conn.execute("DELETE FROM chunks WHERE source_file = ?", (file_path,))
        self.conn.commit()

    def get_all_chunks(self) -> list[dict]:
        cursor = self.conn.execute(
            "SELECT id, text, source_file, header_path, chunk_index, "
            "start_line, end_line, content_type, domain, tags, "
            "token_estimate, content_hash FROM chunks ORDER BY id"
        )
        results = []
        for row in cursor:
            results.append({
                "id": row["id"],
                "text": row["text"],
                "source_file": row["source_file"],
                "header_path": json.loads(row["header_path"] or "[]"),
                "chunk_index": row["chunk_index"],
                "start_line": row["start_line"],
                "end_line": row["end_line"],
                "content_type": row["content_type"] or "prose",
                "domain": row["domain"],
                "tags": json.loads(row["tags"] or "[]"),
                "token_estimate": row["token_estimate"],
                "content_hash": row["content_hash"] or "",
            })
        return results

    def get_all_chunk_hashes(self) -> set[str]:
        cursor = self.conn.execute(
            "SELECT DISTINCT content_hash FROM chunks WHERE content_hash IS NOT NULL"
        )
        return {row["content_hash"] for row in cursor}

    def get_chunks_by_ids(self, chunk_ids: list[int]) -> list[dict]:
        if not chunk_ids:
            return []
        placeholders = ",".join("?" for _ in chunk_ids)
        cursor = self.conn.execute(
            f"SELECT * FROM chunks WHERE id IN ({placeholders})", chunk_ids
        )
        results = {}
        for row in cursor:
            results[row["id"]] = {
                "id": row["id"],
                "text": row["text"],
                "source_file": row["source_file"],
                "header_path": json.loads(row["header_path"] or "[]"),
                "chunk_index": row["chunk_index"],
                "start_line": row["start_line"],
                "end_line": row["end_line"],
                "content_type": row["content_type"] or "prose",
                "domain": row["domain"],
                "tags": json.loads(row["tags"] or "[]"),
                "token_estimate": row["token_estimate"],
                "content_hash": row["content_hash"] or "",
            }
        return [results[cid] for cid in chunk_ids if cid in results]

    def chunk_count(self) -> int:
        cursor = self.conn.execute("SELECT COUNT(*) as cnt FROM chunks")
        return cursor.fetchone()["cnt"]

    def list_domains(self) -> list[str]:
        cursor = self.conn.execute(
            "SELECT DISTINCT domain FROM chunks WHERE domain IS NOT NULL"
        )
        return [row["domain"] for row in cursor]

    def list_source_files(self) -> list[str]:
        cursor = self.conn.execute("SELECT DISTINCT source_file FROM chunks")
        return [row["source_file"] for row in cursor]

    def list_content_types(self) -> dict[str, int]:
        cursor = self.conn.execute(
            "SELECT content_type, COUNT(*) as cnt FROM chunks GROUP BY content_type"
        )
        return {row["content_type"]: row["cnt"] for row in cursor}

    # --- File hash tracking (for incremental indexing) ---

    def get_file_hashes(self) -> dict[str, str]:
        cursor = self.conn.execute("SELECT file_path, hash FROM file_hashes")
        return {row["file_path"]: row["hash"] for row in cursor}

    def set_file_hash(self, file_path: str, file_hash: str):
        import time
        self.conn.execute(
            "INSERT OR REPLACE INTO file_hashes (file_path, hash, last_indexed) "
            "VALUES (?, ?, ?)",
            (file_path, file_hash, time.time()),
        )
        self.conn.commit()

    # --- Index persistence ---

    def save_bm25(self, bm25_obj):
        path = self.store_dir / "bm25_index.pkl"
        with open(path, "wb") as f:
            pickle.dump(bm25_obj, f)

    def load_bm25(self):
        path = self.store_dir / "bm25_index.pkl"
        if not path.exists():
            return None
        with open(path, "rb") as f:
            return pickle.load(f)

    def save_embeddings(self, embeddings):
        import numpy as np
        path = self.store_dir / "embeddings.npy"
        np.save(str(path), embeddings)

    def load_embeddings(self):
        import numpy as np
        path = self.store_dir / "embeddings.npy"
        if not path.exists():
            return None
        return np.load(str(path))

    # --- Metadata ---

    def set_meta(self, key: str, value: str):
        self.conn.execute(
            "INSERT OR REPLACE INTO index_meta (key, value) VALUES (?, ?)",
            (key, value),
        )
        self.conn.commit()

    def get_meta(self, key: str) -> Optional[str]:
        cursor = self.conn.execute(
            "SELECT value FROM index_meta WHERE key = ?", (key,)
        )
        row = cursor.fetchone()
        return row["value"] if row else None

    # --- Aggregate statistics (for dashboard) ---

    def get_aggregate_stats(self) -> dict:
        """
        Compute aggregate statistics across the knowledge base.
        Returns tokens by domain, by file, content type distribution,
        and summary totals.
        """
        stats = {}

        # Tokens by domain
        cursor = self.conn.execute(
            "SELECT COALESCE(domain, 'shared') as domain, "
            "SUM(token_estimate) as total_tokens, COUNT(*) as chunk_count "
            "FROM chunks GROUP BY domain ORDER BY total_tokens DESC"
        )
        stats["tokens_by_domain"] = [
            {"domain": row["domain"], "tokens": row["total_tokens"], "chunks": row["chunk_count"]}
            for row in cursor
        ]

        # Tokens by file
        cursor = self.conn.execute(
            "SELECT source_file, COALESCE(domain, 'shared') as domain, "
            "SUM(token_estimate) as total_tokens, COUNT(*) as chunk_count "
            "FROM chunks GROUP BY source_file ORDER BY total_tokens DESC"
        )
        stats["tokens_by_file"] = [
            {"file": row["source_file"], "domain": row["domain"],
             "tokens": row["total_tokens"], "chunks": row["chunk_count"]}
            for row in cursor
        ]

        # Content type distribution
        cursor = self.conn.execute(
            "SELECT COALESCE(content_type, 'prose') as content_type, "
            "COUNT(*) as count, SUM(token_estimate) as tokens "
            "FROM chunks GROUP BY content_type ORDER BY count DESC"
        )
        stats["content_types"] = [
            {"type": row["content_type"], "count": row["count"], "tokens": row["tokens"]}
            for row in cursor
        ]

        # Totals
        cursor = self.conn.execute(
            "SELECT COUNT(*) as total_chunks, "
            "COALESCE(SUM(token_estimate), 0) as total_tokens, "
            "COALESCE(AVG(token_estimate), 0) as avg_tokens "
            "FROM chunks"
        )
        row = cursor.fetchone()
        stats["total_chunks"] = row["total_chunks"]
        stats["total_tokens"] = row["total_tokens"]
        stats["avg_tokens"] = round(row["avg_tokens"])

        # Domain count
        stats["domain_count"] = len([
            d for d in stats["tokens_by_domain"] if d["domain"] != "shared"
        ])

        # File count
        stats["file_count"] = len(stats["tokens_by_file"])

        return stats

    # --- Graph data (for visualization) ---

    def get_chunk_relationships(self) -> dict:
        """
        Extract relationships between chunks for knowledge graph viz.
        Links chunks that share the same source file or domain.
        Includes full metadata for detail panel display.
        """
        chunks = self.get_all_chunks()
        nodes = []
        edges = []

        file_groups: dict[str, list[int]] = {}
        domain_groups: dict[str, list[int]] = {}

        for c in chunks:
            nodes.append({
                "id": c["id"],
                "label": c["header_path"][-1] if c["header_path"] else c["source_file"],
                "source_file": c["source_file"],
                "domain": c["domain"],
                "content_type": c["content_type"],
                "tokens": c["token_estimate"],
                "header_path": c["header_path"],
                "tags": c["tags"],
                "start_line": c["start_line"],
                "end_line": c["end_line"],
                "content_hash": c["content_hash"],
            })

            file_groups.setdefault(c["source_file"], []).append(c["id"])
            if c["domain"]:
                domain_groups.setdefault(c["domain"], []).append(c["id"])

        # File-level edges (sequential chunks within a file)
        for file_path, chunk_ids in file_groups.items():
            for i in range(len(chunk_ids) - 1):
                edges.append({
                    "source": chunk_ids[i],
                    "target": chunk_ids[i + 1],
                    "type": "sequence",
                })

        # Domain-level edges (shared domain)
        for domain, chunk_ids in domain_groups.items():
            if len(chunk_ids) <= 30:
                for i in range(len(chunk_ids)):
                    for j in range(i + 1, min(i + 3, len(chunk_ids))):
                        edges.append({
                            "source": chunk_ids[i],
                            "target": chunk_ids[j],
                            "type": "domain",
                        })

        return {"nodes": nodes, "edges": edges}

    def close(self):
        self.conn.close()
