"""Remote Streamable HTTP MCP entrypoint."""

from __future__ import annotations

import logging
import sys

from agentpost_sdk import ConfigurationError

from agentpost_mcp.__main__ import _configure_stderr_logging


def main() -> None:
    try:
        import uvicorn

        from agentpost_mcp.remote import RemoteSettings, create_dynamic_remote_app

        settings = RemoteSettings.from_env()
        _configure_stderr_logging(settings.log_level)
        uvicorn.run(
            create_dynamic_remote_app(settings),
            host=settings.host,
            port=settings.port,
            log_level=settings.log_level.casefold(),
        )
    except ImportError as exc:
        sys.stderr.write(
            "AgentPost MCP dependencies are unavailable; install with `agentpost[mcp]`.\n"
        )
        raise SystemExit(2) from exc
    except Exception as exc:
        if isinstance(exc, ConfigurationError):
            sys.stderr.write(f"AgentPost Remote MCP configuration error: {exc}\n")
            raise SystemExit(2) from exc
        logging.getLogger(__name__).error(
            "AgentPost Remote MCP server failed to start type=%s", type(exc).__name__
        )
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
