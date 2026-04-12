"""
API server entry point.

Usage:
    uv run server
    uv run server --reload
"""

import logging
import uvicorn

from app.config import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def main():
    import sys
    reload = "--reload" in sys.argv
    uvicorn.run(
        "app.api.routes:app",
        host=config.api_host,
        port=config.api_port,
        reload=reload,
        reload_dirs=["app"] if reload else None,
    )


if __name__ == "__main__":
    main()
