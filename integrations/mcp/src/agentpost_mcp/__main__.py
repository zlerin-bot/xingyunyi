"""Stdio entrypoint. Standard output is reserved exclusively for MCP JSON-RPC."""

from __future__ import annotations

import logging
import sys

from agentpost_sdk import ConfigurationError


def _configure_stderr_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def main() -> None:
    try:
        from agentpost_mcp.config import Settings

        settings = Settings.from_env()
        _configure_stderr_logging(settings.log_level)

        # Importing the MCP runtime is intentionally delayed so the base AgentPost
        # package remains usable when the optional MCP extra is not installed.
        from agentpost_mcp.server import create_server

        create_server(settings).run("stdio")
    except ImportError as exc:
        sys.stderr.write(
            "AgentPost MCP dependencies are unavailable; install with `agentpost[mcp]`.\n"
        )
        raise SystemExit(2) from exc
    except Exception as exc:
        if isinstance(exc, ConfigurationError):
            sys.stderr.write(f"AgentPost MCP configuration error: {exc}\n")
            raise SystemExit(2) from exc
        logging.getLogger(__name__).error(
            "AgentPost MCP server failed to start type=%s", type(exc).__name__
        )
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
