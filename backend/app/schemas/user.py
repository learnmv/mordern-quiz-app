from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime, date


# User schemas
class UserBase(BaseModel):
    username: str


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class UserLogin(BaseModel):
    username: str
    password: str


# Token schemas
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: Optional[str] = None


# Current user response
class CurrentUser(BaseModel):
    logged_in: bool
    user_id: Optional[int] = None
    username: Optional[str] = None