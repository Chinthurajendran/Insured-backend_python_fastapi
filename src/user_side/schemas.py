from pydantic import BaseModel,EmailStr,Field
import uuid
from datetime import datetime


class UserCreate(BaseModel):
    username:str
    email: EmailStr
    password :  str
    confirm_password : str


class UserModel(BaseModel):
    user_id : uuid.UUID
    username:str
    email: EmailStr
    password_hash:str = Field(exclude=True)
    created_at :datetime
    updated_at :datetime

class UserLoginModel(BaseModel):
    email: str
    password:str


class GoogleAuthModel(BaseModel):
    token: str