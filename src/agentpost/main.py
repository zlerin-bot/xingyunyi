from __future__ import annotations

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError

from agentpost.api.errors import http_exception_handler, validation_exception_handler
from agentpost.api.middleware import request_context_middleware
from agentpost.api.routes.agents import router as agents_router
from agentpost.api.routes.directory import router as directory_router
from agentpost.api.routes.messages import router as messages_router
from agentpost.api.routes.system import router as system_router
from agentpost.config import Settings, get_settings
from agentpost.db import Database
from agentpost.observability.logging import configure_logging


def create_app(settings: Settings | None = None, database: Database | None = None) -> FastAPI:
    runtime_settings = settings or get_settings()
    runtime_database = database or Database(runtime_settings.database_url)
    configure_logging(runtime_settings.log_level)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        runtime_database.dispose()

    app = FastAPI(
        title="AgentPost",
        version="0.1.0",
        description="Asynchronous agent-to-agent messaging infrastructure",
        lifespan=lifespan,
    )
    app.state.settings = runtime_settings
    app.state.database = runtime_database
    app.middleware("http")(request_context_middleware)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.include_router(system_router)
    app.include_router(agents_router)
    app.include_router(directory_router)
    app.include_router(messages_router)
    return app


app = create_app()


def run() -> None:
    uvicorn.run("agentpost.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    run()
