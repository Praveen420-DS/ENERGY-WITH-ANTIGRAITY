from pydantic import BaseModel, EmailStr
from typing import Optional

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str]

class UserCreate(UserBase):
    password: str

class UserRead(UserBase):
    id: str
    role: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str
