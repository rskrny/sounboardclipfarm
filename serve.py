"""Start the soundboardclipfarm API server.

Usage:
    python serve.py              # default: http://127.0.0.1:8000
    python serve.py --port 9000
    python serve.py --reload     # auto-reload on code changes (dev mode)

API docs available at http://127.0.0.1:8000/docs once running.
"""

import argparse
import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the clipfarm API server.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Auto-reload on code changes")
    args = parser.parse_args()

    print(f"Starting soundboardclipfarm API on http://{args.host}:{args.port}")
    print(f"API docs: http://{args.host}:{args.port}/docs")
    uvicorn.run(
        "clipfarm.service:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
