from pydantic import BaseModel


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


class LLMConnectionResult(BaseModel):
    success: bool
    model: str
    message: str
    latency_ms: int

