from sqlmodel import SQLModel, Field, Column
from datetime import date, datetime
import uuid
import sqlalchemy.dialects.postgresql as pg
from sqlalchemy.sql import func
from enum import Enum as PyEnum
from sqlalchemy import Enum


# Define Enum class
class ApprovalStatus(str, PyEnum):
    approved = "approved"
    processing = "processing"
    rejected = "rejected"

class AgentTable(SQLModel, table=True):
    __tablename__ = "agenttable"

    agent_id: uuid.UUID = Field(
        sa_column=Column(
            pg.UUID, 
            primary_key=True, 
            default=uuid.uuid4, 
            nullable=False
        )
    )
    agent_profile: str = Field(default=None, nullable=True)
    agent_idproof: str = Field(default=None, nullable=True)
    agent_name: str = Field(unique=True, nullable=False)
    agent_email: str = Field(default=None, nullable=True)
    password: str = Field(default=None, nullable=True)
    gender: str = Field(default="Male", nullable=True)
    phone: str = Field(default="7034345848", nullable=True)
    date_of_birth: date = Field(default=date(1997, 12, 15), nullable=True)
    city: str = Field(default="Kochi", max_length=100, nullable=True)
    latitude: float = Field(default=0.0, nullable=True)
    longitude: float = Field(default=0.0, nullable=True)
    agent_login_status: bool = Field(default=False, nullable=True)
    busy_status: bool = Field(default=False, nullable=True)
    # approval_status: bool = Field(default=False, nullable=True)
        # Change approval_status to Enum
    approval_status: ApprovalStatus = Field(
        sa_column=Column(Enum(ApprovalStatus), default=ApprovalStatus.processing)
    )
    is_agent: bool = Field(default=False, nullable=True)
    create_at: datetime = Field(sa_column=Column(
        pg.TIMESTAMP, default=datetime.utcnow))
    update_at: datetime = Field(sa_column=Column(
        pg.TIMESTAMP, default=datetime.utcnow))
    def __repr__(self):
        return f"<AgentTable {self.agent_name}>"
