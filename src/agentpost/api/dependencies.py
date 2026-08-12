from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from agentpost.config import Settings
from agentpost.db import Database


def get_database(request: Request) -> Database:
    return request.app.state.database


def get_runtime_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_session(database: Annotated[Database, Depends(get_database)]):
    yield from database.session()


DatabaseDep = Annotated[Database, Depends(get_database)]
SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_runtime_settings)]
