"""
Configuration for the retrieval system.
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RetrievalConfig:
    """All retrieval system settings in one place."""

    # Paths
    knowledge_root: Path = Path(".")
    store_dir: Path = Path("retrieval/store")

    # Directories to index (relative to knowledge_root)
    index_dirs: list[str] = field(default_factory=lambda: [
        "prompts/context",
        "prompts/domains",
    ])

    # File patterns to include
    include_patterns: list[str] = field(default_factory=lambda: ["*.md"])

    # Files/dirs to skip
    exclude_patterns: list[str] = field(default_factory=lambda: [
        "INDEX.md",
        "TEMPLATE.md",
        "archive/*",
    ])

    # Chunking
    chunk_max_tokens: int = 512
    chunk_overlap_tokens: int = 64
    split_on_headers: bool = True
    min_chunk_length: int = 50  # characters

    # BM25
    bm25_k1: float = 1.5
    bm25_b: float = 0.75

    # Embeddings
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384
    use_semantic: bool = True  # False = BM25-only "lite mode"

    # Search
    default_top_k: int = 10
    bm25_weight: float = 0.4
    semantic_weight: float = 0.6
    rerank_top_n: int = 20  # candidates before fusion

    # SQLite
    db_path: Optional[Path] = None

    def __post_init__(self):
        self.knowledge_root = Path(self.knowledge_root)
        self.store_dir = Path(self.store_dir)
        if self.db_path is None:
            self.db_path = self.store_dir / "metadata.db"

    @classmethod
    def from_yaml(cls, path: Path) -> "RetrievalConfig":
        """Load config from a YAML file. Falls back to defaults for missing keys."""
        import yaml
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
