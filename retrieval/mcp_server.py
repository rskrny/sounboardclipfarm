"""
MCP Server for the Context Engineering Retrieval System.

Exposes search, index, and stats as MCP tools that Claude Code
can call natively. Run with:

    python -m retrieval.mcp_server

Or add to your Claude Code MCP config.
"""

import json
import sys
from pathlib import Path

from .config import RetrievalConfig


def _get_config() -> RetrievalConfig:
    """Load config, defaulting to current directory as knowledge root."""
    root = Path.cwd()
    config_path = root / "retrieval" / "config.yaml"
    if config_path.exists():
        config = RetrievalConfig.from_yaml(config_path)
    else:
        config = RetrievalConfig()
    config.knowledge_root = root
    config.store_dir = root / "retrieval" / "store"
    config.db_path = config.store_dir / "metadata.db"
    return config


def handle_search(params: dict) -> dict:
    """Search the knowledge base."""
    from .searcher import Searcher

    config = _get_config()
    searcher = Searcher(config)

    query = params.get("query", "")
    top_k = params.get("top_k", 10)
    domain = params.get("domain")
    bm25_only = params.get("bm25_only", False)

    if bm25_only:
        results = searcher.search_bm25_only(query, top_k=top_k)
    else:
        results = searcher.search(query=query, top_k=top_k, domain_filter=domain)

    searcher.close()

    return {
        "results": [
            {
                "text": r.text,
                "source_file": r.source_file,
                "header_path": r.header_path,
                "domain": r.domain,
                "tags": r.tags,
                "score": round(r.score, 4),
                "context_label": r.context_label,
            }
            for r in results
        ],
        "count": len(results),
        "query": query,
    }


def handle_index(params: dict) -> dict:
    """Rebuild the search index."""
    from .indexer import build_index

    config = _get_config()
    stats = build_index(config, verbose=False)
    return stats


def handle_stats(params: dict) -> dict:
    """Get index statistics."""
    from .searcher import Searcher

    config = _get_config()
    searcher = Searcher(config)
    stats = searcher.get_stats()
    searcher.close()
    return stats


def handle_get_context(params: dict) -> dict:
    """
    Retrieve context for a given query.

    Returns the top results formatted as a context block
    ready to inject into an LLM prompt.
    """
    from .searcher import Searcher

    config = _get_config()
    searcher = Searcher(config)

    query = params.get("query", "")
    max_tokens = params.get("max_tokens", 2000)
    domain = params.get("domain")

    results = searcher.search(query=query, top_k=20, domain_filter=domain)
    searcher.close()

    # Build context block within token budget
    context_parts = []
    token_count = 0

    for r in results:
        chunk_tokens = len(r.text) // 4
        if token_count + chunk_tokens > max_tokens:
            break

        context_parts.append(
            f"--- {r.context_label} (score: {r.score:.3f}) ---\n{r.text}"
        )
        token_count += chunk_tokens

    return {
        "context": "\n\n".join(context_parts),
        "sources": [r.source_file for r in results[:len(context_parts)]],
        "token_estimate": token_count,
        "chunks_used": len(context_parts),
    }


# MCP protocol implementation (stdio JSON-RPC)

TOOLS = {
    "search_knowledge": {
        "description": (
            "Search the knowledge base using hybrid BM25 + semantic retrieval. "
            "Returns ranked chunks from the context engineering system."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results to return (default: 10)",
                    "default": 10,
                },
                "domain": {
                    "type": "string",
                    "description": "Filter results to a specific domain",
                },
                "bm25_only": {
                    "type": "boolean",
                    "description": "Use BM25 only (faster, no ML)",
                    "default": False,
                },
            },
            "required": ["query"],
        },
        "handler": handle_search,
    },
    "get_context": {
        "description": (
            "Retrieve relevant context for a query, formatted as a context block "
            "ready for LLM consumption. Respects a token budget."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What context do you need?",
                },
                "max_tokens": {
                    "type": "integer",
                    "description": "Maximum tokens in the context block (default: 2000)",
                    "default": 2000,
                },
                "domain": {
                    "type": "string",
                    "description": "Filter to a specific domain",
                },
            },
            "required": ["query"],
        },
        "handler": handle_get_context,
    },
    "rebuild_index": {
        "description": (
            "Rebuild the search index. Run this after adding new knowledge files."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
        "handler": handle_index,
    },
    "index_stats": {
        "description": "Get statistics about the current search index.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
        "handler": handle_stats,
    },
}


def _send(msg: dict):
    """Send a JSON-RPC message to stdout."""
    data = json.dumps(msg)
    sys.stdout.write(f"Content-Length: {len(data)}\r\n\r\n{data}")
    sys.stdout.flush()


def _read() -> dict:
    """Read a JSON-RPC message from stdin."""
    headers = {}
    while True:
        line = sys.stdin.readline()
        if line == "\r\n" or line == "\n":
            break
        if ":" in line:
            key, val = line.split(":", 1)
            headers[key.strip()] = val.strip()

    length = int(headers.get("Content-Length", 0))
    if length == 0:
        return {}
    body = sys.stdin.read(length)
    return json.loads(body)


def run_server():
    """Run the MCP server using stdio transport."""
    while True:
        try:
            msg = _read()
        except (EOFError, KeyboardInterrupt):
            break

        if not msg:
            break

        method = msg.get("method")
        msg_id = msg.get("id")
        params = msg.get("params", {})

        if method == "initialize":
            _send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "context-retrieval",
                        "version": "0.1.0",
                    },
                },
            })

        elif method == "notifications/initialized":
            pass  # no response needed

        elif method == "tools/list":
            tools_list = []
            for name, tool in TOOLS.items():
                tools_list.append({
                    "name": name,
                    "description": tool["description"],
                    "inputSchema": tool["inputSchema"],
                })
            _send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": tools_list},
            })

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})

            if tool_name in TOOLS:
                try:
                    result = TOOLS[tool_name]["handler"](tool_args)
                    _send({
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "content": [{
                                "type": "text",
                                "text": json.dumps(result, indent=2),
                            }],
                        },
                    })
                except Exception as e:
                    _send({
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "content": [{
                                "type": "text",
                                "text": f"Error: {str(e)}",
                            }],
                            "isError": True,
                        },
                    })
            else:
                _send({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32601,
                        "message": f"Unknown tool: {tool_name}",
                    },
                })


if __name__ == "__main__":
    run_server()
