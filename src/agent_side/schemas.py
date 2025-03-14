from pydantic import BaseModel,EmailStr,Field
import uuid
from datetime import date, datetime
from typing import Optional


class AgentCreateRequest(BaseModel):
    username:str
    email: EmailStr
    password :  str
    confirm_password : str
    phone: str
    date_of_birth:date 
    gender:str
    city:str

class AgentCreateResponse(BaseModel):
    agent_id : uuid.UUID
    username:str
    email: EmailStr
    password_hash:str = Field(exclude=True)
    phone: str
    date_of_birth:date  
    gender:str
    city:str
    id_proof:str
    created_at :datetime
    updated_at :datetime


class AgentLoginModel(BaseModel):
    agentid: str
    password:str
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ExistingUserPolicyRequest(BaseModel):
    email: EmailStr
    policy_name: str
    policy_type: str
    nominee_name: str
    nominee_relationship: str

class NewUserPolicyRequest(BaseModel):
    username:str
    email: EmailStr
    phone: str
    date_of_birth:date  
    gender:str
    city:str
    marital_status:str
    annual_income:str
    policy_name: str
    policy_type: str
    nominee_name: str
    nominee_relationship: str


class AgentProfileCreateRequest(BaseModel):
    username: str
    email: str
    phone: str
    gender: str
    city: str
    date_of_birth: date  

class AgentPasswordrecovery (BaseModel):
    agentID: str

class RestpasswordModel(BaseModel):
    agentid: str
    password:str