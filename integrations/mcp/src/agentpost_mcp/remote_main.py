"""Remote Streamable HTTP MCP entrypoint."""

from __future__ import annotations

import logging
import sys

from agentpost_sdk import ConfigurationError

from agentpost_mcp.__main__ import _configure_stderr_logging


def main() -> None:
    try:
        from mcp.server.transport_security import TransportSecuritySettings

        from agentpost_mcp.remote import RemoteSettings, create_remote_server

        settings = RemoteSettings.from_env()
        _configure_stderr_logging(settings.log_level)
        create_remote_server(settings).run(
            "streamable-http",
            host=settings.host,
            port=settings.port,
            streamable_http_path="/mcp",
            json_response=True,
            stateless_http=True,
            transport_security=TransportSecuritySettings(
                enable_dns_rebinding_protection=True,
                allowed_hosts=list(settings.allowed_hosts),
                allowed_origins=list(settings.allowed_origins),
            ),
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
