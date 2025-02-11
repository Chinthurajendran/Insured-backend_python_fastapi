from pydantic import BaseModel,EmailStr,Field
import uuid
from datetime import date, datetime
from typing import Optional

# class AgentCreate(BaseModel):
#     username:str
#     email: EmailStr
#     password :  str
#     confirm_password : str
#     phone: str
#     date_of_birth:date 
#     gender:str
#     city:str


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


# PolicyCreateRequest
# PolicyCreateResponse

# class AgentModel(BaseModel):
#     agent_id : uuid.UUID
#     username:str
#     email: EmailStr
#     password_hash:str = Field(exclude=True)
#     phone: str
#     date_of_birth:date  
#     gender:str
#     city:str
#     id_proof:str
#     created_at :datetime
#     updated_at :datetime


class AgentLoginModel(BaseModel):
    email: EmailStr
    password:str