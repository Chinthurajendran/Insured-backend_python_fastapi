from pydantic import BaseModel
import uuid
from datetime import date, datetime

class Admin_login(BaseModel):
    username :str
    password:str

class PolicyCreateResponse(BaseModel):
    policy_uid: uuid.UUID
    policy_id: str
    policy_name: str
    policy_type: str
    id_proof: bool = False
    passbook: bool = False
    photo: bool = False
    pan_card: bool = False
    income_proof: bool = False
    nominee_address_proof: bool = False
    coverage: str
    settlement: str
    premium_amount: str
    age_group: str
    income_range: str
    description: str = ""
    create_at: datetime
    update_at: datetime


class PolicyCreateRequest(BaseModel):
    policy_name: str
    policy_type: str
    id_proof: bool = False
    passbook: bool = False
    photo: bool = False
    pan_card: bool = False
    income_proof: bool = False
    nominee_address_proof: bool = False
    coverage: str
    settlement: str
    premium_amount: str
    age_group: str
    income_range: str
    description: str = ""


class PolicyediteRequest(BaseModel):
    policy_name: str
    policy_type: str
    id_proof: bool = False
    passbook: bool = False
    photo: bool = False
    pan_card: bool = False
    income_proof: bool = False
    nominee_address_proof: bool = False
    coverage: str
    settlement: str
    premium_amount: str
    age_group: str
    income_range: str
    description: str = ""


class PolicyeinfocreateRequest(BaseModel):
    policyinfo_name: str
    titledescription: str
    description: str
