from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Union

class SignupIn(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None

class SigninIn(BaseModel):
    email: str
    password: str

class RequestOtpIn(BaseModel):
    email: str
    full_name: Optional[str] = None

class VerifyOtpIn(BaseModel):
    email: str
    code: str
    full_name: Optional[str] = None

class AnalyzeIn(BaseModel):
    target_role: str
    skills: List[str]

class JobAnalyzeIn(BaseModel):
    target_role: Optional[str] = None
    job_description: str
    user_skills: Optional[List[str]] = None

class CompareIn(BaseModel):
    roles: List[str]
    user_skills: Optional[List[str]] = None

class RoadmapIn(BaseModel):
    target_role: str
    skills: List[str]
    days: int = 30

class ChatIn(BaseModel):
    message: str
    target_role: Optional[str] = None
    missing_skills: Optional[List[str]] = None

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict
