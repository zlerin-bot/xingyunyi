from __future__ import annotations

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError

from agentpost.api.errors import http_exception_handler, validation_exception_handler
from agentpost.api.middleware import request_context_middleware
from agentpost.api.routes.access import router as access_router
from agentpost.api.routes.admin import router as admin_router
from agentpost.api.routes.agents import router as agents_router
from agentpost.api.routes.approvals import router as approvals_router
from agentpost.api.routes.attachments import router as attachments_router
from agentpost.api.routes.directory import router as directory_router
from agentpost.api.routes.enterprise_oidc import router as enterprise_oidc_router
from agentpost.api.routes.human_auth import router as human_auth_router
from agentpost.api.routes.messages import router as messages_router
from agentpost.api.routes.oauth import router as oauth_router
from agentpost.api.routes.onboarding import router as onboarding_router
from agentpost.api.routes.orbit import router as orbit_router
from agentpost.api.routes.organization_governance import router as organization_governance_router
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
        title="星云驿 · 云驿 API",
        version="0.1.0",
        description="云驿异步 Agent 通信网络与星轨人类控制面",
        lifespan=lifespan,
    )
    app.state.settings = runtime_settings
    app.state.database = runtime_database
    app.middleware("http")(request_context_middleware)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.include_router(system_router)
    app.include_router(oauth_router)
    app.include_router(admin_router)
    app.include_router(orbit_router)
    app.include_router(human_auth_router)
    app.include_router(enterprise_oidc_router)
    app.include_router(organization_governance_router)
    app.include_router(approvals_router)
    app.include_router(onboarding_router)
    app.include_router(agents_router)
    app.include_router(access_router)
    app.include_router(attachments_router)
    app.include_router(directory_router)
    app.include_router(messages_router)
    return app


app = create_app()


def run() -> None:
    uvicorn.run("agentpost.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    run()
