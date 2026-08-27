from pydantic import BaseModel
from pydantic import Field


class HealthResponse(BaseModel):
    status: str
    app_name: str
    database: str
    llm_configured: bool


class LLMConfigStatus(BaseModel):
    configured: bool
    base_url: str
    model: str
    api_key_present: bool


class LLMConfigUpdate(BaseModel):
    base_url: str = Field(min_length=1, max_length=500)
    api_key: str = Field(min_length=1, max_length=1000)
    model: str = Field(min_length=1, max_length=200)


class LLMConnectionResult(BaseModel):
    success: bool
    model: str
    message: str
    latency_ms: int
