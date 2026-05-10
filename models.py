from pydantic import BaseModel
from typing import Optional, List

class VerifyRequest(BaseModel):
    task_type: str        # "code" | "text" | "file" | "image" | "script"
    intent: str           # what user originally asked
    ai_claim: str         # what AI said it did
    output: str           # actual output to verify
    language: Optional[str] = "python"
    file_paths: Optional[List[str]] = []

class VerifyResponse(BaseModel):
    id: str
    verified: bool
    check_type: str
    confidence: float
    reason: str
    retry_prompt: str
    cost: str
    task_type: str
    timestamp: str
    retries_used: Optional[int] = 0

class VerificationRecord(BaseModel):
    id: str
    api_key: str
    task_type: str
    verified: bool
    confidence: float
    reason: str
    retry_prompt: str
    cost: str
    timestamp: str
    intent: str