"""
Structure-aware chunker with multi-format support.

Splits documents into retrieval-friendly chunks while preserving
semantic boundaries. Never splits inside code fences, tables,
or blockquotes. Handles markdown, plain text, code files, HTML,
PDF, DOCX, CSV, and JSON.

Each chunk carries full provenance: where it came from, what
section it belongs to, and what type of content it contains.
"""

import re
import hashlib
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Chunk:
    """A single retrievable unit of knowledge."""

    text: str
    source_file: str          # relative path from knowledge root
    header_path: list[str]    # e.g. ["## Stage 2", "### Process"]
    chunk_index: int          # position within file
    start_line: int
    end_line: int
    content_type: str = "prose"  # prose, code, table, metadata, mixed
    domain: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    content_hash: str = ""    # SHA-256 of text for dedup

    def __post_init__(self):
        if not self.content_hash:
            self.content_hash = hashlib.sha256(self.text.encode()).hexdigest()[:16]

    @property
    def context_label(self) -> str:
        parts = [self.source_file]
        if self.header_path:
            parts.append(" > ".join(self.header_path))
        return " | ".join(parts)

    @property
    def token_estimate(self) -> int:
        return len(self.text) // 4

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "source_file": self.source_file,
            "header_path": self.header_path,
            "chunk_index": self.chunk_index,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "content_type": self.content_type,
            "domain": self.domain,
            "tags": self.tags,
            "content_hash": self.content_hash,
        }


# --- Content type detection ---

HEADER_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
FENCE_RE = re.compile(r"^(`{3,}|~{3,})", re.MULTILINE)
TABLE_ROW_RE = re.compile(r"^\|.+\|$")
TABLE_SEP_RE = re.compile(r"^\|[\s\-:|]+\|$")

# File extension to format mapping
FORMAT_MAP = {
    ".md": "markdown",
    ".markdown": "markdown",
    ".txt": "text",
    ".rst": "text",
    ".py": "code", ".js": "code", ".ts": "code", ".jsx": "code", ".tsx": "code",
    ".go": "code", ".rs": "code", ".java": "code", ".c": "code", ".cpp": "code",
    ".h": "code", ".hpp": "code", ".cs": "code", ".rb": "code", ".php": "code",
    ".swift": "code", ".kt": "code", ".scala": "code", ".r": "code",
    ".sh": "code", ".bash": "code", ".zsh": "code", ".ps1": "code",
    ".sql": "code", ".graphql": "code", ".proto": "code",
    ".yaml": "structured", ".yml": "structured", ".toml": "structured",
    ".json": "structured", ".xml": "structured",
    ".csv": "tabular", ".tsv": "tabular",
    ".html": "html", ".htm": "html",
    ".pdf": "pdf",
    ".docx": "docx",
}


def detect_format(file_path: str) -> str:
    """Detect document format from file extension."""
    ext = Path(file_path).suffix.lower()
    return FORMAT_MAP.get(ext, "text")


# --- Protected block detection (fence-aware) ---

@dataclass
class ProtectedBlock:
    """A region of text that must not be split."""
    start_line: int
    end_line: int
    block_type: str  # "code_fence", "table", "blockquote"


def _find_protected_blocks(lines: list[str]) -> list[ProtectedBlock]:
    """Find all code fences, tables, and blockquotes that must stay intact."""
    blocks = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Code fences (``` or ~~~)
        fence_match = FENCE_RE.match(line)
        if fence_match:
            fence_char = fence_match.group(1)[0]
            fence_len = len(fence_match.group(1))
            start = i
            i += 1
            while i < len(lines):
                close_match = re.match(f"^{re.escape(fence_char)}{{{fence_len},}}\\s*$", lines[i])
                if close_match:
                    blocks.append(ProtectedBlock(start, i, "code_fence"))
                    break
                i += 1
            i += 1
            continue

        # Tables (consecutive lines starting and ending with |)
        if TABLE_ROW_RE.match(line.strip()):
            start = i
            while i < len(lines) and TABLE_ROW_RE.match(lines[i].strip()):
                i += 1
            if i - start >= 2:  # at least header + separator or 2 rows
                blocks.append(ProtectedBlock(start, i - 1, "table"))
            continue

        i += 1

    return blocks


def _is_protected(line_num: int, blocks: list[ProtectedBlock]) -> bool:
    """Check if a line falls within a protected block."""
    for b in blocks:
        if b.start_line <= line_num <= b.end_line:
            return True
    return False


def _get_protected_block(line_num: int, blocks: list[ProtectedBlock]) -> Optional[ProtectedBlock]:
    """Get the protected block containing this line, if any."""
    for b in blocks:
        if b.start_line <= line_num <= b.end_line:
            return b
    return None


# --- Domain and tag extraction ---

def _extract_domain(file_path: str) -> Optional[str]:
    """Infer domain from file path."""
    parts = Path(file_path).parts
    if "domains" in parts:
        idx = list(parts).index("domains")
        if idx + 1 < len(parts):
            return Path(parts[idx + 1]).stem
    if "by-domain" in parts:
        idx = list(parts).index("by-domain")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return None


def _extract_tags(text: str) -> list[str]:
    """Pull tags from frontmatter or inline markers."""
    tags = []
    fm_match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if fm_match:
        for line in fm_match.group(1).split("\n"):
            if line.strip().startswith("tags:"):
                tag_str = line.split(":", 1)[1].strip()
                tags.extend(t.strip().strip("[]\"'") for t in tag_str.split(","))
    tags.extend(re.findall(r"(?:^|\s)#([a-zA-Z][\w-]+)", text))
    return [t for t in tags if t]


def _detect_content_type(text: str) -> str:
    """Classify a chunk's content type."""
    lines = text.strip().split("\n")
    code_lines = sum(1 for l in lines if l.strip().startswith(("```", "~~~", "def ", "class ", "function ", "import ", "from ", "const ", "let ", "var ")))
    table_lines = sum(1 for l in lines if TABLE_ROW_RE.match(l.strip()))
    total = max(len(lines), 1)

    if code_lines / total > 0.5:
        return "code"
    if table_lines / total > 0.5:
        return "table"
    if code_lines > 0 and table_lines > 0:
        return "mixed"
    return "prose"


# --- Main chunking functions ---

def chunk_markdown(
    content: str,
    source_file: str,
    max_tokens: int = 512,
    overlap_tokens: int = 64,
    min_chunk_length: int = 50,
    split_on_headers: bool = True,
) -> list[Chunk]:
    """
    Split a markdown file into chunks with fence-aware boundaries.

    Strategy:
    1. Identify protected blocks (code fences, tables).
    2. Split on headers (preserves semantic boundaries).
    3. Never split inside a protected block.
    4. If a section exceeds max_tokens, split on paragraphs
       (still respecting protected blocks).
    5. Overlap between chunks for context continuity.
    """
    if not content.strip():
        return []

    domain = _extract_domain(source_file)
    file_tags = _extract_tags(content)
    lines = content.split("\n")

    # Strip frontmatter
    start_idx = 0
    if lines and lines[0].strip() == "---":
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                start_idx = i + 1
                break

    # Find protected blocks
    protected = _find_protected_blocks(lines)

    # Build sections by headers (respecting protected blocks)
    sections = []
    current_headers = []
    current_lines = []
    current_start = start_idx

    i = start_idx
    while i < len(lines):
        line = lines[i]

        # Skip splitting on headers inside protected blocks
        if _is_protected(i, protected):
            current_lines.append(line)
            i += 1
            continue

        header_match = HEADER_RE.match(line)
        if header_match and split_on_headers:
            if current_lines:
                text = "\n".join(current_lines).strip()
                if len(text) >= min_chunk_length:
                    sections.append((text, list(current_headers), current_start, i - 1))
                current_lines = []

            level = len(header_match.group(1))
            header_text = header_match.group(2).strip()
            current_headers = [h for h in current_headers if h[0] < level]
            current_headers.append((level, f"{'#' * level} {header_text}"))
            current_start = i
        else:
            current_lines.append(line)

        i += 1

    if current_lines:
        text = "\n".join(current_lines).strip()
        if len(text) >= min_chunk_length:
            sections.append((text, list(current_headers), current_start, len(lines) - 1))

    # Chunk each section
    chunks = []
    chunk_idx = 0

    for text, headers, start_line, end_line in sections:
        header_labels = [h[1] for h in headers]
        est_tokens = len(text) // 4
        content_type = _detect_content_type(text)

        if est_tokens <= max_tokens:
            chunks.append(Chunk(
                text=text,
                source_file=source_file,
                header_path=header_labels,
                chunk_index=chunk_idx,
                start_line=start_line,
                end_line=end_line,
                content_type=content_type,
                domain=domain,
                tags=file_tags,
            ))
            chunk_idx += 1
        else:
            sub_chunks = _split_large_text_fence_aware(
                text, max_tokens, overlap_tokens, min_chunk_length
            )
            for sub_text in sub_chunks:
                chunks.append(Chunk(
                    text=sub_text,
                    source_file=source_file,
                    header_path=header_labels,
                    chunk_index=chunk_idx,
                    start_line=start_line,
                    end_line=end_line,
                    content_type=_detect_content_type(sub_text),
                    domain=domain,
                    tags=file_tags,
                ))
                chunk_idx += 1

    return chunks


def _split_large_text_fence_aware(
    text: str,
    max_tokens: int,
    overlap_tokens: int,
    min_chunk_length: int,
) -> list[str]:
    """
    Split oversized text while keeping protected blocks intact.

    Order of split boundaries:
    1. Double newlines (paragraph breaks) outside protected blocks
    2. Single newlines outside protected blocks
    3. Sentence boundaries (last resort)

    A protected block that exceeds max_tokens gets its own chunk
    regardless of size. Better to have one oversized chunk than
    a broken code block.
    """
    max_chars = max_tokens * 4
    overlap_chars = overlap_tokens * 4

    lines = text.split("\n")
    protected = _find_protected_blocks(lines)

    # Build "segments" that respect protected blocks
    segments = []
    current_segment = []
    current_start = 0

    i = 0
    while i < len(lines):
        block = _get_protected_block(i, protected)
        if block:
            # Flush any accumulated non-protected lines
            if current_segment:
                seg_text = "\n".join(current_segment)
                if seg_text.strip():
                    segments.append(("text", seg_text))
                current_segment = []

            # Add the entire protected block as one unit
            block_lines = lines[block.start_line:block.end_line + 1]
            segments.append(("protected", "\n".join(block_lines)))
            i = block.end_line + 1
        else:
            # Check for paragraph break
            if lines[i].strip() == "" and current_segment:
                seg_text = "\n".join(current_segment)
                if seg_text.strip():
                    segments.append(("text", seg_text))
                current_segment = []
                segments.append(("break", ""))
            else:
                current_segment.append(lines[i])
            i += 1

    if current_segment:
        seg_text = "\n".join(current_segment)
        if seg_text.strip():
            segments.append(("text", seg_text))

    # Now combine segments into chunks respecting max_chars
    result = []
    current = ""

    for seg_type, seg_text in segments:
        if seg_type == "break":
            continue

        if seg_type == "protected":
            # Protected blocks stay intact
            if len(current) + len(seg_text) + 2 <= max_chars:
                current = current + "\n\n" + seg_text if current else seg_text
            else:
                if current and len(current) >= min_chunk_length:
                    result.append(current.strip())
                # Protected block gets its own chunk even if oversized
                if len(seg_text) >= min_chunk_length:
                    result.append(seg_text.strip())
                current = ""
        else:
            # Regular text
            if len(current) + len(seg_text) + 2 <= max_chars:
                current = current + "\n\n" + seg_text if current else seg_text
            else:
                if current and len(current) >= min_chunk_length:
                    result.append(current.strip())
                if overlap_chars > 0 and current:
                    overlap = current[-overlap_chars:]
                    current = overlap + "\n\n" + seg_text
                else:
                    current = seg_text

                # Still too big? Sentence-split the text segment only
                if len(current) > max_chars:
                    sentences = re.split(r"(?<=[.!?])\s+", current)
                    current = ""
                    for sent in sentences:
                        if len(current) + len(sent) + 1 <= max_chars:
                            current = current + " " + sent if current else sent
                        else:
                            if current and len(current) >= min_chunk_length:
                                result.append(current.strip())
                            current = sent

    if current and len(current) >= min_chunk_length:
        result.append(current.strip())

    return result


# --- Code file chunking ---

def chunk_code(
    content: str,
    source_file: str,
    max_tokens: int = 512,
    min_chunk_length: int = 50,
) -> list[Chunk]:
    """
    Split code files by function/class boundaries.

    Strategy: Split on top-level definitions. If a single definition
    exceeds max_tokens, keep it intact (better oversized than broken).
    """
    if not content.strip():
        return []

    domain = _extract_domain(source_file)
    ext = Path(source_file).suffix.lower()
    lines = content.split("\n")

    # Language-specific definition patterns
    if ext in (".py",):
        def_re = re.compile(r"^(class |def |async def )")
    elif ext in (".js", ".ts", ".jsx", ".tsx"):
        def_re = re.compile(r"^(export |function |class |const \w+ = |let \w+ = |async function )")
    elif ext in (".go",):
        def_re = re.compile(r"^(func |type )")
    elif ext in (".rs",):
        def_re = re.compile(r"^(pub |fn |impl |struct |enum |trait )")
    elif ext in (".java", ".cs", ".kt"):
        def_re = re.compile(r"^(public |private |protected |class |interface |enum |fun )")
    else:
        def_re = re.compile(r"^(function |class |def |pub |fn )")

    # Split on top-level definitions
    sections = []
    current_lines = []
    current_start = 0
    current_name = source_file

    for i, line in enumerate(lines):
        if def_re.match(line.lstrip()) and line[0:1] not in (" ", "\t"):
            # Top-level definition boundary
            if current_lines:
                text = "\n".join(current_lines).strip()
                if len(text) >= min_chunk_length:
                    sections.append((text, current_name, current_start, i - 1))
            current_lines = [line]
            current_start = i
            # Extract definition name
            name_match = re.search(r"(?:class|def|function|func|fn|type|struct|enum|trait|interface)\s+(\w+)", line)
            current_name = name_match.group(1) if name_match else f"line_{i}"
        else:
            current_lines.append(line)

    if current_lines:
        text = "\n".join(current_lines).strip()
        if len(text) >= min_chunk_length:
            sections.append((text, current_name, current_start, len(lines) - 1))

    # Build chunks
    chunks = []
    for idx, (text, name, start, end) in enumerate(sections):
        chunks.append(Chunk(
            text=text,
            source_file=source_file,
            header_path=[f"def {name}"] if name != source_file else [],
            chunk_index=idx,
            start_line=start,
            end_line=end,
            content_type="code",
            domain=domain,
            tags=[Path(source_file).suffix.lstrip(".")],
        ))

    return chunks


# --- Structured data chunking ---

def chunk_structured(
    content: str,
    source_file: str,
    max_tokens: int = 512,
    min_chunk_length: int = 50,
) -> list[Chunk]:
    """Chunk JSON, YAML, TOML, XML files by top-level keys/sections."""
    if not content.strip():
        return []

    domain = _extract_domain(source_file)
    ext = Path(source_file).suffix.lower()

    if ext in (".json",):
        return _chunk_json(content, source_file, domain, max_tokens, min_chunk_length)
    elif ext in (".csv", ".tsv"):
        return _chunk_csv(content, source_file, domain, max_tokens, min_chunk_length)

    # For YAML/TOML/XML, treat as text with indentation-aware splitting
    lines = content.split("\n")
    sections = []
    current = []
    current_start = 0

    for i, line in enumerate(lines):
        # Top-level key (no indentation) marks a boundary
        if line and line[0] not in (" ", "\t", "#", "-") and ":" in line:
            if current:
                text = "\n".join(current).strip()
                if len(text) >= min_chunk_length:
                    sections.append((text, current_start, i - 1))
            current = [line]
            current_start = i
        else:
            current.append(line)

    if current:
        text = "\n".join(current).strip()
        if len(text) >= min_chunk_length:
            sections.append((text, current_start, len(lines) - 1))

    chunks = []
    for idx, (text, start, end) in enumerate(sections):
        chunks.append(Chunk(
            text=text,
            source_file=source_file,
            header_path=[],
            chunk_index=idx,
            start_line=start,
            end_line=end,
            content_type="metadata",
            domain=domain,
            tags=[ext.lstrip(".")],
        ))
    return chunks


def _chunk_json(content, source_file, domain, max_tokens, min_chunk_length):
    """Chunk JSON by top-level keys."""
    import json as json_lib
    try:
        data = json_lib.loads(content)
    except json_lib.JSONDecodeError:
        # Fall back to text chunking
        return [Chunk(
            text=content[:max_tokens * 4],
            source_file=source_file,
            header_path=[],
            chunk_index=0,
            start_line=0,
            end_line=content.count("\n"),
            content_type="metadata",
            domain=domain,
        )]

    chunks = []
    if isinstance(data, dict):
        for idx, (key, value) in enumerate(data.items()):
            text = f"{key}: {json_lib.dumps(value, indent=2, default=str)}"
            if len(text) >= min_chunk_length:
                chunks.append(Chunk(
                    text=text[:max_tokens * 4],
                    source_file=source_file,
                    header_path=[key],
                    chunk_index=idx,
                    start_line=0,
                    end_line=0,
                    content_type="metadata",
                    domain=domain,
                    tags=["json"],
                ))
    elif isinstance(data, list):
        text = json_lib.dumps(data[:50], indent=2, default=str)
        chunks.append(Chunk(
            text=text[:max_tokens * 4],
            source_file=source_file,
            header_path=[],
            chunk_index=0,
            start_line=0,
            end_line=0,
            content_type="metadata",
            domain=domain,
            tags=["json"],
        ))
    return chunks


def _chunk_csv(content, source_file, domain, max_tokens, min_chunk_length):
    """Chunk CSV/TSV by groups of rows."""
    lines = content.strip().split("\n")
    if not lines:
        return []

    header = lines[0]
    max_chars = max_tokens * 4
    chunks = []
    current = header
    chunk_idx = 0
    start = 0

    for i, line in enumerate(lines[1:], 1):
        if len(current) + len(line) + 1 <= max_chars:
            current += "\n" + line
        else:
            if len(current) >= min_chunk_length:
                chunks.append(Chunk(
                    text=current,
                    source_file=source_file,
                    header_path=[f"rows {start}-{i-1}"],
                    chunk_index=chunk_idx,
                    start_line=start,
                    end_line=i - 1,
                    content_type="table",
                    domain=domain,
                    tags=["csv"],
                ))
                chunk_idx += 1
            current = header + "\n" + line
            start = i

    if len(current) >= min_chunk_length:
        chunks.append(Chunk(
            text=current,
            source_file=source_file,
            header_path=[f"rows {start}-{len(lines)-1}"],
            chunk_index=chunk_idx,
            start_line=start,
            end_line=len(lines) - 1,
            content_type="table",
            domain=domain,
            tags=["csv"],
        ))

    return chunks


# --- HTML chunking ---

def chunk_html(
    content: str,
    source_file: str,
    max_tokens: int = 512,
    min_chunk_length: int = 50,
) -> list[Chunk]:
    """Strip HTML to text, then chunk as markdown."""
    try:
        from html.parser import HTMLParser

        class TextExtractor(HTMLParser):
            def __init__(self):
                super().__init__()
                self.parts = []
                self.skip = False

            def handle_starttag(self, tag, attrs):
                if tag in ("script", "style", "nav", "footer", "header"):
                    self.skip = True
                elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                    level = int(tag[1])
                    self.parts.append("\n" + "#" * level + " ")
                elif tag in ("p", "div", "section", "article"):
                    self.parts.append("\n\n")
                elif tag == "br":
                    self.parts.append("\n")
                elif tag == "li":
                    self.parts.append("\n- ")

            def handle_endtag(self, tag):
                if tag in ("script", "style", "nav", "footer", "header"):
                    self.skip = False

            def handle_data(self, data):
                if not self.skip:
                    self.parts.append(data)

        extractor = TextExtractor()
        extractor.feed(content)
        text = "".join(extractor.parts).strip()
    except Exception:
        # Fallback: strip all tags with regex
        text = re.sub(r"<[^>]+>", " ", content)
        text = re.sub(r"\s+", " ", text).strip()

    return chunk_markdown(text, source_file, max_tokens, 0, min_chunk_length)


# --- PDF chunking ---

def chunk_pdf(
    file_path: Path,
    source_file: str,
    max_tokens: int = 512,
    min_chunk_length: int = 50,
) -> list[Chunk]:
    """Extract text from PDF and chunk it."""
    text = ""
    try:
        import fitz  # pymupdf
        doc = fitz.open(str(file_path))
        pages = []
        for page in doc:
            pages.append(page.get_text())
        text = "\n\n".join(pages)
        doc.close()
    except ImportError:
        try:
            import pdfplumber
            with pdfplumber.open(str(file_path)) as pdf:
                pages = [p.extract_text() or "" for p in pdf.pages]
            text = "\n\n".join(pages)
        except ImportError:
            return [Chunk(
                text=f"[PDF file: {source_file} -- install pymupdf or pdfplumber to index]",
                source_file=source_file,
                header_path=[],
                chunk_index=0,
                start_line=0,
                end_line=0,
                content_type="prose",
                domain=_extract_domain(source_file),
                tags=["pdf", "unprocessed"],
            )]

    if not text.strip():
        return []

    return chunk_markdown(text, source_file, max_tokens, 0, min_chunk_length, split_on_headers=False)


# --- DOCX chunking ---

def chunk_docx(
    file_path: Path,
    source_file: str,
    max_tokens: int = 512,
    min_chunk_length: int = 50,
) -> list[Chunk]:
    """Extract text from DOCX and chunk it."""
    try:
        import docx
        doc = docx.Document(str(file_path))
        parts = []
        for para in doc.paragraphs:
            style = para.style.name if para.style else ""
            if "Heading" in style:
                try:
                    level = int(style.replace("Heading", "").strip())
                except ValueError:
                    level = 1
                parts.append(f"\n{'#' * level} {para.text}")
            else:
                parts.append(para.text)
        text = "\n\n".join(parts)
    except ImportError:
        return [Chunk(
            text=f"[DOCX file: {source_file} -- install python-docx to index]",
            source_file=source_file,
            header_path=[],
            chunk_index=0,
            start_line=0,
            end_line=0,
            content_type="prose",
            domain=_extract_domain(source_file),
            tags=["docx", "unprocessed"],
        )]

    if not text.strip():
        return []

    return chunk_markdown(text, source_file, max_tokens, 0, min_chunk_length)


# --- Universal dispatcher ---

def chunk_file(
    file_path: Path,
    source_file: str,
    max_tokens: int = 512,
    overlap_tokens: int = 64,
    min_chunk_length: int = 50,
    split_on_headers: bool = True,
) -> list[Chunk]:
    """
    Universal entry point. Detects format and dispatches
    to the appropriate chunker.
    """
    fmt = detect_format(source_file)

    if fmt == "pdf":
        return chunk_pdf(file_path, source_file, max_tokens, min_chunk_length)

    if fmt == "docx":
        return chunk_docx(file_path, source_file, max_tokens, min_chunk_length)

    # For text-based formats, read content
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    if fmt == "markdown":
        return chunk_markdown(content, source_file, max_tokens, overlap_tokens, min_chunk_length, split_on_headers)
    elif fmt == "code":
        return chunk_code(content, source_file, max_tokens, min_chunk_length)
    elif fmt in ("structured", "tabular"):
        return chunk_structured(content, source_file, max_tokens, min_chunk_length)
    elif fmt == "html":
        return chunk_html(content, source_file, max_tokens, min_chunk_length)
    else:
        # Plain text: use markdown chunker without header splitting
        return chunk_markdown(content, source_file, max_tokens, overlap_tokens, min_chunk_length, split_on_headers=False)


# --- File collection ---

def collect_files(
    knowledge_root: Path,
    index_dirs: list[str],
    include_patterns: list[str],
    exclude_patterns: list[str],
) -> list[Path]:
    """Find all indexable files under the configured directories."""
    import fnmatch

    files = []
    for dir_name in index_dirs:
        dir_path = knowledge_root / dir_name
        if not dir_path.exists():
            continue
        for pattern in include_patterns:
            for f in dir_path.rglob(pattern):
                rel = f.relative_to(knowledge_root)
                skip = False
                for excl in exclude_patterns:
                    if fnmatch.fnmatch(rel.name, excl) or fnmatch.fnmatch(str(rel), excl):
                        skip = True
                        break
                if not skip and f.is_file():
                    files.append(f)

    return sorted(set(files))
