from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SessionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    era_id: str
    status: str
    state_version: int
    created_at: datetime
    updated_at: datetime


class SessionDetail(SessionRead):
    player_state: dict[str, Any]


class SessionRename(BaseModel):
    name: str = Field(min_length=1, max_length=200)

