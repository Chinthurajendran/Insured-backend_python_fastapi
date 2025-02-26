from sqlmodel import SQLModel, Field, Column, Field, ForeignKey,Relationship
from datetime import date, datetime
import uuid
import sqlalchemy.dialects.postgresql as pg


class policytable(SQLModel, table=True):
    __tablename__ = "policytable"
    policy_uid: uuid.UUID = Field(
        sa_column=Column(
            pg.UUID,
            nullable=False,
            primary_key=True,
            default=uuid.uuid4
        )
    )
    policy_id: str = Field(unique=True, nullable=False)
    policy_name: str = Field(unique=True, nullable=False)
    policy_type: str = Field(nullable=False)

    id_proof: bool = Field(default=False)
    passbook: bool = Field(default=False)
    photo: bool = Field(default=False)
    pan_card: bool = Field(default=False)
    income_proof: bool = Field(default=False)
    nominee_address_proof: bool = Field(default=False)

    coverage: str = Field(nullable=False)
    settlement: str = Field(nullable=False)
    premium_amount: str = Field(nullable=False)

    age_group: str = Field(nullable=False)
    income_range: str = Field(nullable=False)

    description: str = Field(default="", nullable=True)
    role: str = Field(default="admin", max_length=20,nullable=True)

    delete_status: bool = Field(default=False)
    block_status: bool = Field(default=False)
    create_at: datetime = Field(sa_column=Column(
        pg.TIMESTAMP, default=datetime.utcnow))
    update_at: datetime = Field(sa_column=Column(
        pg.TIMESTAMP, default=datetime.utcnow))

    def __repr__(self):
        return f"<policytable {self.policy_name}>"
    

class PolicyDetails(SQLModel, table=True):
    __tablename__ = "policydetails"
    
    policydetails_uid: uuid.UUID = Field(
        sa_column=Column(pg.UUID, primary_key=True, default=uuid.uuid4, nullable=False)
    )
    
    user_id: uuid.UUID = Field(
        sa_column=Column(pg.UUID, ForeignKey("usertable.user_id"), nullable=False)
    )
    
    agent_id: uuid.UUID = Field(
        sa_column=Column(pg.UUID, ForeignKey("agenttable.agent_id"), nullable=False)
    )

    policy_name: str = Field(nullable=False)
    policy_type: str = Field(nullable=False)
    nominee_name: str = Field(nullable=False)
    nominee_relationship: str = Field(nullable=False)
    coverage: str = Field(nullable=False)
    settlement: str = Field(nullable=False)
    premium_amount: str = Field(nullable=False)
    monthly_amount: str = Field(nullable=False)
    age: str = Field(nullable=False)
    income_range: str = Field(nullable=False)

    id_proof: bool = Field(default=False)
    passbook: bool = Field(default=False)
    photo: bool = Field(default=False)
    pan_card: bool = Field(default=False)
    income_proof: bool = Field(default=False)
    nominee_address_proof: bool = Field(default=False)

    feedback: str = Field(default="", nullable=True)
    policy_status: bool = Field(default=False) 
    payment_status: bool = Field(default=False)
    date_of_payment: datetime = Field(default=None, nullable=True)

    role: str = Field(default="admin", max_length=20, nullable=True)

    delete_status: bool = Field(default=False)
    block_status: bool = Field(default=False)
    create_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow))
    update_at: datetime = Field(sa_column=Column(pg.TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow))

    def __repr__(self):
        return f"<PolicyDetails {self.policy_name}>"