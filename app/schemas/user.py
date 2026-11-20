# app/schemas/user.py
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List
from datetime import datetime

# --- Base Schemas ---
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern="^[a-zA-Z0-9_]+$")
    full_name: str = Field(..., min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    role: str = Field(default="viewer", pattern="^(admin|manager|sales|warehouse|accountant|viewer)$")

# --- Create Schema (توسط ادمین) ---
class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=128)

# --- Update Schema ---
class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    role: Optional[str] = Field(None, pattern="^(admin|manager|sales|warehouse|accountant|viewer)$")
    is_active: Optional[bool] = None

# --- Change Password Schema ---
class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=6)
    new_password: str = Field(..., min_length=6, max_length=128)

# --- Response Schema ---
class UserResponse(BaseModel):
    id: int
    username: str
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str
    is_active: bool
    is_superuser: bool
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

# --- List Response ---
class UserListResponse(BaseModel):
    total: int
    users: List[UserResponse]

# --- Auth Schemas ---
class LoginRequest(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse