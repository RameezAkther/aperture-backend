from pydantic import BaseModel, EmailStr
from typing import Optional, Dict

class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: Optional[str] = None
    auth_provider: Optional[str] = "email"
    google_token: Optional[str] = None
    preferences: Optional[Dict] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str
