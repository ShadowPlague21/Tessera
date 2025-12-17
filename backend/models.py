from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
from decimal import Decimal

class JobRequest(BaseModel):
    frontend: str  # "telegram", "discord", "web"
    bot_id: Optional[str] = None
    capability: str  # "image", "video", "text", "audio"
    user_ref: str  # "telegram:123456" or "web:user_id"
    params: Dict[str, Any]
    reply_context: Optional[Dict[str, Any]] = None

class JobResponse(BaseModel):
    job_id: str
    status: str
    estimated_time_seconds: int
    cost_tokens: Decimal
    queue_position: int

class Artifact(BaseModel):
    type: str
    path: Optional[str]
    url: Optional[str]
    metadata: Optional[Dict[str, Any]] = {}

class JobCompletionData(BaseModel):
    job_id: str
    status: str # "completed", "failed"
    execution_time_seconds: float
    artifacts: List[Artifact] = []
    error: Optional[Dict[str, Any]] = None
