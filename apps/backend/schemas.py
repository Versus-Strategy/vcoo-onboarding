from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime


# ── VCOO ──

class VCOOCreate(BaseModel):
    name: Optional[str] = None
    modules: Optional[list[str]] = ["core"]
    # ["core", "office", "mail", "planner", "developer"]


class VCOOResponse(BaseModel):
    id: str
    name: Optional[str]
    status: str = "active"
    created_at: Optional[str] = None
    modules: Optional[list[str]] = ["core"]
    onboarding_url: Optional[str] = None


# ── Onboarding State ──

class OnboardingProgress(BaseModel):
    total: int
    done: int


class OnboardingError(BaseModel):
    step: str
    error: str
    timestamp: Optional[str] = None


class OnboardingStateResponse(BaseModel):
    vcoo_id: str
    name: Optional[str]
    modules: list[str]
    step: str
    status: str
    completed: list[str]
    errors: list[dict]
    retry_count: dict
    progress: OnboardingProgress
    agent: Optional[dict] = None
    install_command: Optional[str] = None


# ── Agent Result ──

class AgentResultRequest(BaseModel):
    cmd_id: str
    step: str
    status: str  # "ok" | "error"
    output: str = ""
    details: Optional[dict] = None


class AgentResultResponse(BaseModel):
    ack: bool
    cmd_id: str
    next_step: Optional[str] = None
    status: Optional[str] = None  # for 409: "already_reported"


# ── Heartbeat ──

class AgentHeartbeatRequest(BaseModel):
    agent_id: str
    vcoo_id: str


# ── Command ──

class EnqueueCommandRequest(BaseModel):
    command: str
    step: Optional[str] = None
    ttl_seconds: Optional[int] = 300


# ── Auth / Login ──

class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: dict


# ── Client auth ──

class ClientRegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    token: str


class ClientLoginRequest(BaseModel):
    email: str
    password: str


class ClientResponse(BaseModel):
    id: str
    email: str
    name: str | None = None
    vcoo_id: str | None = None
    created_at: str | None = None
