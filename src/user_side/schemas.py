from pydantic import BaseModel,EmailStr,Field
import uuid
from datetime import datetime,date
from typing import Optional


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


class Passwordrecovery (BaseModel):
    email: str


class GoogleAuthModel(BaseModel):
    token: str

class ProfileCreateRequest(BaseModel):
    username: str
    email: str
    phone: str
    marital_status: str
    gender: str
    city: str
    date_of_birth: date  
    annual_income: str


class PolicyDetails(BaseModel):
    policy_name: str
    policy_type: str
    id_proof: bool
    passbook: bool
    photo: bool
    pan_card: bool
    income_proof: bool
    nominee_address_proof: bool
    coverage: str
    settlement: str
    premium_amount: str
    income_range: str

class PolicyRegistration(BaseModel):
    nominee_name: str
    nominee_relationship: str
